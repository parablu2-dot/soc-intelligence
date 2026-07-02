"""
Amkor Technology 뉴스 크롤러 — OSAT, 첨단 패키징 신호 수집.
소스 1 (EDGAR 8-K): CIK 1047466 (NASDAQ: AMKR)
소스 2 (HTML 폴백): https://ir.amkor.com/news-releases
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import parse_rss, extract_tags
from crawlers.common.schema import RefinedSignal

_EDGAR_RSS = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    "&CIK=1047466&type=8-K&dateb=&owner=include&count=40&search_text=&output=atom"
)
_EDGAR_HEADERS = {
    "User-Agent": "SoCIntelligenceBot/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}
_HTML_URL = "https://ir.amkor.com/news-releases"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SoCIntelligenceBot/1.0)"}
_SOURCE_NAME = "Amkor Technology"


class AmkorCrawler(BaseCrawler):
    axis = "packaging"
    company = "amkor"

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
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category="packaging",
                headline=item["title"],
                url=item["url"],
                published_date=item["published_date"],
                source=_SOURCE_NAME,
                tags=extract_tags(item["title"]),
                summary=None,
            ))
        return signals

    def _parse_html(self, raw: str) -> list[RefinedSignal]:
        soup = BeautifulSoup(raw, "lxml")
        signals = []
        seen = set()
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            href = a["href"]
            if len(text) > 20 and ("news" in href or "release" in href) and href not in seen:
                seen.add(href)
                url = href if href.startswith("http") else f"https://ir.amkor.com{href}"
                signals.append(RefinedSignal(
                    axis=self.axis,
                    company=self.company,
                    category="packaging",
                    headline=text,
                    url=url,
                    published_date=date.today(),
                    source=_SOURCE_NAME,
                    tags=extract_tags(text),
                    summary=None,
                ))
        return signals[:20]


if __name__ == "__main__":
    AmkorCrawler().run()
