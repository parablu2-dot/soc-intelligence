"""
SK hynix 뉴스 크롤러 — HBM4/HBM3E, 첨단 메모리 패키징 신호 수집.
소스 (HTML): https://news.skhynix.com/
enabled: false (config.yaml) — 활성화 전 소스 검증 필요
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_NEWS_URL = "https://news.skhynix.com/"
_FALLBACK_URL = "https://investor.skhynix.com/en/news/press-release"
_SOURCE_NAME = "SK hynix News"

_HYNIX_KEYWORDS = [
    "hbm", "hbm4", "hbm3e", "hbm3", "dram", "nand", "memory", "bandwidth",
    "advanced package", "chip", "processor", "ai memory", "compute",
    "data center", "datacenter", "semiconductor", "packaging",
]


def _is_hynix_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _HYNIX_KEYWORDS) or is_soc_relevant(text)


class SkHynixCrawler(BaseCrawler):
    axis = "hpc_datacenter"
    company = "sk_hynix"

    def fetch(self) -> str:
        for url in [_NEWS_URL, _FALLBACK_URL]:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                if resp.ok and len(resp.text) > 500:
                    return resp.text
            except Exception:
                continue
        return ""

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        soup = BeautifulSoup(raw, "lxml")
        signals = []
        items = soup.select("article, .news-card, .post, li.item") or _fallback_links(soup)
        for item in items:
            title_el = item.select_one("h2, h3, h4, .title, .headline")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date, .published")

            if item.name == "a":
                title, href = item.get_text(strip=True), item.get("href", "")
            elif title_el and link_el:
                title, href = title_el.get_text(strip=True), link_el["href"]
            else:
                continue

            if not title or not _is_hynix_relevant(title):
                continue

            url = href if href.startswith("http") else f"https://news.skhynix.com{href}"
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
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    SkHynixCrawler().run()
