"""
Qualcomm 크롤러 — Snapdragon / 모바일 AP 관련 신호 수집.
소스 1: SEC EDGAR 8-K (공시 RSS) — 공개 정적 소스
소스 2 (폴백): https://investor.qualcomm.com/news-events/press-releases
"""
import requests
from bs4 import BeautifulSoup
from datetime import date

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

# Qualcomm CIK: 804328
_EDGAR_RSS = (
    "https://www.sec.gov/cgi-bin/browse-edgar"
    "?action=getcompany&CIK=804328&type=8-K"
    "&dateb=&owner=include&count=20&search_text=&output=atom"
)
_HTML_URL = "https://investor.qualcomm.com/news-events/press-releases"
_SOURCE_NAME = "Qualcomm"

_EDGAR_HEADERS = {
    "User-Agent": "SoCIntelligenceBot/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}


class QualcommCrawler(BaseCrawler):
    axis = "mobile_ap"
    company = "qualcomm"

    def fetch(self) -> str:
        try:
            resp = requests.get(_EDGAR_RSS, headers=_EDGAR_HEADERS, timeout=30)
            if resp.ok and ("<feed" in resp.text[:300] or "<rss" in resp.text[:300]):
                return resp.text
        except Exception:
            pass
        resp = requests.get(_HTML_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, raw: str) -> list[RefinedSignal]:
        if "<feed" in raw[:300] or "<rss" in raw[:300]:
            return self._parse_rss(raw)
        return self._parse_html(raw)

    def _parse_rss(self, raw: str) -> list[RefinedSignal]:
        signals = []
        for item in parse_rss(raw):
            combined = f"{item['title']} {item['summary']}"
            if not is_soc_relevant(combined):
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
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if len(text) < 30 or not is_soc_relevant(text):
                continue
            href = a["href"]
            url = href if href.startswith("http") else f"https://investor.qualcomm.com{href}"
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
        return signals


if __name__ == "__main__":
    QualcommCrawler().run()
