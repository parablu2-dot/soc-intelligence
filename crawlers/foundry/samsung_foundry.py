"""
Samsung Foundry 뉴스 크롤러 — 3nm GAA, 공정 노드 발표 신호 수집.
소스 1 (HTML): https://news.samsungsemiconductor.com/global/category/foundry/
소스 2 (HTML 폴백): https://news.samsungsemiconductor.com/global/
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_PRIMARY_URL = "https://news.samsungsemiconductor.com/global/category/foundry/"
_FALLBACK_URL = "https://news.samsungsemiconductor.com/global/"
_SOURCE_NAME = "Samsung Semiconductor News"

_FOUNDRY_KEYWORDS = [
    "foundry", "process", "3nm", "2nm", "4nm", "5nm", "gaa", "gate-all-around",
    "sf3", "sf4", "sf5", "manufacturing", "wafer", "node", "fab", "chiplet",
    "cowos", "advanced packaging",
]


def _is_foundry_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _FOUNDRY_KEYWORDS) or is_soc_relevant(text)


class SamsungFoundryCrawler(BaseCrawler):
    axis = "foundry"
    company = "samsung_foundry"

    def fetch(self) -> str:
        for url in [_PRIMARY_URL, _FALLBACK_URL]:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.ok and len(resp.text) > 1000:
                    return resp.text
            except Exception:
                continue
        return ""

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        soup = BeautifulSoup(raw, "lxml")
        signals = []
        items = soup.select("article, .news-card, .post-item") or _fallback_links(soup)
        for item in items:
            title_el = item.select_one("h2, h3, h4, .title, .entry-title")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date, .entry-date")

            if item.name == "a":
                title, href = item.get_text(strip=True), item.get("href", "")
            elif title_el and link_el:
                title, href = title_el.get_text(strip=True), link_el["href"]
            else:
                continue

            if not title or len(title) < 10 or not _is_foundry_relevant(title):
                continue

            url = href if href.startswith("http") else f"https://news.samsungsemiconductor.com{href}"
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
    SamsungFoundryCrawler().run()
