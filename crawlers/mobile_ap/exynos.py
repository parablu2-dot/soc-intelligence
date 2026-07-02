"""
Exynos / Samsung 반도체 신호 수집.
소스 1 (RSS 시도): https://news.samsung.com/global/feed/press-release
소스 2 (HTML 폴백): https://semiconductor.samsung.com/us/news/
"""
import requests
from bs4 import BeautifulSoup
from datetime import date

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, fetch_html,
    is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_RSS_URLS = [
    "https://news.samsung.com/global/feed/press-release",
    "https://news.samsung.com/global/rss",
]
_HTML_URL = "https://semiconductor.samsung.com/us/"
_SOURCE_NAME = "Samsung Newsroom"

_EXYNOS_KEYWORDS = [
    "exynos", "samsung foundry", "samsung semiconductor",
    "galaxy chip", "modem", "5g chip", "hbm", "dram",
    "silicon", "chip", "soc", "processor",
]


class ExynosCrawler(BaseCrawler):
    axis = "mobile_ap"
    company = "exynos"

    def fetch(self) -> str:
        for rss_url in _RSS_URLS:
            try:
                resp = requests.get(rss_url, headers=HEADERS, timeout=20)
                if resp.ok and ("<rss" in resp.text[:500] or "<feed" in resp.text[:500]):
                    return resp.text
            except Exception:
                continue
        return fetch_html(_HTML_URL)

    def parse(self, raw: str) -> list[RefinedSignal]:
        if "<rss" in raw[:500] or "<feed" in raw[:500]:
            return self._parse_rss(raw)
        return self._parse_html(raw)

    def _parse_rss(self, raw: str) -> list[RefinedSignal]:
        signals = []
        for item in parse_rss(raw):
            combined = f"{item['title']} {item['summary']}".lower()
            if not any(kw in combined for kw in _EXYNOS_KEYWORDS):
                continue
            full = f"{item['title']} {item['summary']}"
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(full),
                headline=item["title"],
                url=item["url"],
                published_date=item["published_date"],
                source=_SOURCE_NAME,
                tags=extract_tags(full),
                summary=item["summary"][:500] if item["summary"] else None,
            ))
        return signals

    def _parse_html(self, raw: str) -> list[RefinedSignal]:
        soup = BeautifulSoup(raw, "lxml")
        signals = []

        items = (
            soup.select(".news-item")
            or soup.select("article")
            or soup.select(".press-release")
            or _fallback_links(soup)
        )

        for item in items:
            title_el = item.select_one("h2, h3, h4, .title, .news-title")
            link_el  = item.select_one("a[href]")
            date_el  = item.select_one("time, .date, span.date")

            if not title_el or not link_el:
                if item.name == "a":
                    title = item.get_text(strip=True)
                    href  = item.get("href", "")
                else:
                    continue
            else:
                title = title_el.get_text(strip=True)
                href  = link_el["href"]

            url = href if href.startswith("http") else f"https://semiconductor.samsung.com/us{href}"
            pub_date = _parse_date_text(date_el.get_text(strip=True) if date_el else "")

            if not is_soc_relevant(title):
                continue

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
        if len(text) > 20 and href not in seen and is_soc_relevant(text):
            seen.add(href)
            items.append(a)
    return items


def _parse_date_text(text: str) -> date:
    from datetime import datetime
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    ExynosCrawler().run()
