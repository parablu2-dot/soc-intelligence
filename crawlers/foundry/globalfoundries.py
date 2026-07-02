"""
GlobalFoundries 뉴스 크롤러 — 공정 개발, 고객 수주 신호 수집.
소스 1 (EDGAR 8-K): CIK 1826397 (NASDAQ: GFS)
소스 2 (HTML 폴백): https://gf.com/news/
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import parse_rss, extract_tags, infer_category
from crawlers.common.schema import RefinedSignal

_EDGAR_RSS = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    "&CIK=1826397&type=8-K&dateb=&owner=include&count=40&search_text=&output=atom"
)
_EDGAR_HEADERS = {
    "User-Agent": "SoCIntelligenceBot/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}
_HTML_URL = "https://gf.com/news/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SoCIntelligenceBot/1.0)"}
_SOURCE_NAME = "GlobalFoundries"


class GlobalFoundriesCrawler(BaseCrawler):
    axis = "foundry"
    company = "globalfoundries"

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
                category=infer_category(item["title"]),
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
        items = soup.select("article, .news-item, .press-release") or []
        for item in items:
            title_el = item.select_one("h2, h3, h4, .title")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date")
            if not (title_el and link_el):
                continue
            title = title_el.get_text(strip=True)
            href = link_el["href"]
            url = href if href.startswith("http") else f"https://gf.com{href}"
            pub_date = _parse_date_text(date_el.get_text(strip=True) if date_el else "")
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(title),
                headline=title,
                url=url,
                published_date=pub_date,
                source=_SOURCE_NAME,
                tags=extract_tags(title),
                summary=None,
            ))
        return signals


def _parse_date_text(text: str) -> date:
    from datetime import datetime
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    GlobalFoundriesCrawler().run()
