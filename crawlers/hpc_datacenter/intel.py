"""
Intel 뉴스룸 RSS 크롤러 — Intel Foundry / Gaudi / Xeon 관련 신호 수집.
소스 1 (RSS 시도): https://newsroom.intel.com/feed/
소스 2 (HTML 폴백): https://newsroom.intel.com/news
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, fetch_html,
    is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_RSS_URLS = [
    "https://newsroom.intel.com/feed/",
    "https://www.intel.com/content/www/us/en/newsroom/news/press-rss.html",
]
_HTML_URL = "https://newsroom.intel.com/news"
_SOURCE_NAME = "Intel Newsroom"


class IntelCrawler(BaseCrawler):
    axis = "hpc_datacenter"
    company = "intel"

    def fetch(self) -> str:
        for rss_url in _RSS_URLS:
            try:
                resp = requests.get(rss_url, headers=HEADERS, timeout=30)
                if resp.ok and ("<rss" in resp.text[:500] or "<feed" in resp.text[:500]):
                    return resp.text
            except Exception:
                continue
        return fetch_html(_HTML_URL)

    def parse(self, raw: str) -> list[RefinedSignal]:
        if raw.strip().startswith("<?xml") or "<rss" in raw[:500] or "<feed" in raw[:500]:
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

        items = (
            soup.select(".news-article")
            or soup.select("article")
            or soup.select(".press-release")
            or _fallback_links(soup)
        )

        for item in items:
            title_el = item.select_one("h2, h3, h4, .title, .article-title")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date, .pub-date")

            if not title_el or not link_el:
                if item.name == "a":
                    title = item.get_text(strip=True)
                    href = item.get("href", "")
                else:
                    continue
            else:
                title = title_el.get_text(strip=True)
                href = link_el["href"]

            url = href if href.startswith("http") else f"https://newsroom.intel.com{href}"
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
        if len(text) > 30 and href not in seen and is_soc_relevant(text):
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
    IntelCrawler().run()
