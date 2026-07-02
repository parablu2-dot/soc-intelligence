"""
ASE Technology Holding 뉴스 크롤러 — OSAT, 첨단 패키징 신호 수집.
소스 1 (EDGAR 6-K): CIK 1399067 (NYSE: ASX)
소스 2 (HTML 폴백): https://www.aseglobal.com/en/news/
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import parse_rss, is_soc_relevant, extract_tags
from crawlers.common.schema import RefinedSignal

_EDGAR_RSS = (
    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
    "&CIK=1399067&type=6-K&dateb=&owner=include&count=40&search_text=&output=atom"
)
_EDGAR_HEADERS = {
    "User-Agent": "SoCIntelligenceBot/1.0 (contact@example.com)",
    "Accept-Encoding": "gzip, deflate",
}
_HTML_URL = "https://www.aseglobal.com/en/news/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SoCIntelligenceBot/1.0)"}
_SOURCE_NAME = "ASE Technology"

_PKG_KEYWORDS = [
    "packaging", "advanced packaging", "flip chip", "wirebond", "sip",
    "system in package", "fan-out", "fan out", "cowos", "hbm", "chiplet",
    "osat", "assembly", "test", "semiconductor", "chip",
]


def _is_pkg_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _PKG_KEYWORDS) or is_soc_relevant(text)


class AseCrawler(BaseCrawler):
    axis = "packaging"
    company = "ase"

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
        items = soup.select("article, .news-item") or _fallback_links(soup)
        for item in items:
            title_el = item.select_one("h2, h3, h4, .title")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date")

            if item.name == "a":
                title, href = item.get_text(strip=True), item.get("href", "")
            elif title_el and link_el:
                title, href = title_el.get_text(strip=True), link_el["href"]
            else:
                continue

            if not title or not _is_pkg_relevant(title):
                continue

            url = href if href.startswith("http") else f"https://www.aseglobal.com{href}"
            pub_date = _parse_date_text(date_el.get_text(strip=True) if date_el else "")
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category="packaging",
                headline=title,
                url=url,
                published_date=pub_date,
                source=_SOURCE_NAME,
                tags=extract_tags(title),
                summary=None,
            ))
        return signals


def _fallback_links(soup: BeautifulSoup) -> list:
    seen = set()
    items = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if len(text) > 20 and href not in seen:
            seen.add(href)
            items.append(a)
    return items


def _parse_date_text(text: str) -> date:
    from datetime import datetime
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    AseCrawler().run()
