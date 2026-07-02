"""
Tesla 뉴스 크롤러 — Dojo 슈퍼컴퓨터, FSD 칩, 커스텀 AI SoC 신호 수집.
소스 1 (EDGAR 8-K): CIK 1318605 (NASDAQ: TSLA)
소스 2 (HTML 폴백): https://ir.tesla.com/news-events/press-releases
enabled: false (config.yaml) — SoC 관련 발표 빈도 낮아 검토 후 활성화
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import parse_rss, is_soc_relevant, extract_tags, infer_category
from crawlers.common.schema import RefinedSignal

_EDGAR_RSS = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    "&CIK=1318605&type=8-K&dateb=&owner=include&count=40&search_text=&output=atom"
)
_EDGAR_HEADERS = {
    "User-Agent": "SoCIntelligenceBot/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}
_HTML_URL = "https://ir.tesla.com/news-events/press-releases"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SoCIntelligenceBot/1.0)"}
_SOURCE_NAME = "Tesla IR"

_TESLA_KEYWORDS = [
    "dojo", "fsd chip", "full self-driving chip", "hw4", "hardware 4",
    "ai training", "custom silicon", "neural network chip", "supercomputer",
    "compute", "inference", "training cluster", "ai accelerator",
]


def _is_tesla_soc_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _TESLA_KEYWORDS) or is_soc_relevant(text)


class TeslaCrawler(BaseCrawler):
    axis = "hpc_datacenter"
    company = "tesla"

    def fetch(self) -> str:
        try:
            resp = requests.get(_EDGAR_RSS, headers=_EDGAR_HEADERS, timeout=30)
            if resp.ok and "<feed" in resp.text[:500]:
                return resp.text
        except Exception:
            pass
        try:
            resp = requests.get(_HTML_URL, headers=_HEADERS, timeout=30)
            if resp.ok:
                return resp.text
        except Exception:
            pass
        return ""

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        if "<feed" in raw[:500] or "<rss" in raw[:500]:
            return self._parse_rss(raw)
        return self._parse_html(raw)

    def _parse_rss(self, raw: str) -> list[RefinedSignal]:
        signals = []
        for item in parse_rss(raw):
            combined = f"{item['title']} {item['summary']}"
            if not _is_tesla_soc_relevant(combined):
                continue
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(combined),
                headline=item["title"],
                url=item["url"],
                published_date=item["published_date"],
                source=_SOURCE_NAME,
                tags=extract_tags(combined),
                summary=item["summary"][:500] if item["summary"] else None,
            ))
        return signals

    def _parse_html(self, raw: str) -> list[RefinedSignal]:
        soup = BeautifulSoup(raw, "lxml")
        signals = []
        seen = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if len(text) > 20 and href not in seen and _is_tesla_soc_relevant(text):
                seen.add(href)
                url = href if href.startswith("http") else f"https://ir.tesla.com{href}"
                signals.append(RefinedSignal(
                    axis=self.axis,
                    company=self.company,
                    category=infer_category(text),
                    headline=text,
                    url=url,
                    published_date=date.today(),
                    source=_SOURCE_NAME,
                    tags=extract_tags(text),
                    summary=None,
                ))
        return signals[:20]


if __name__ == "__main__":
    TeslaCrawler().run()
