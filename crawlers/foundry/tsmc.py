"""
TSMC 뉴스룸 크롤러 — 공정 노드 발표, 캐파 신호 수집.
소스 1 (HTML): https://pr.tsmc.com/english/news
소스 2 (HTML 폴백): https://investor.tsmc.com/english/news/press-releases
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_NEWS_URL = "https://pr.tsmc.com/english/news"
_IR_URL = "https://investor.tsmc.com/english/news/press-releases"
_SOURCE_NAME = "TSMC Newsroom"


class TsmcCrawler(BaseCrawler):
    axis = "foundry"
    company = "tsmc"

    def fetch(self) -> str:
        for url in [_NEWS_URL, _IR_URL]:
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
        return self._parse_html(raw)

    def _parse_html(self, raw: str) -> list[RefinedSignal]:
        soup = BeautifulSoup(raw, "lxml")
        signals = []
        items = (
            soup.select(".news-item, .press-item, article")
            or _fallback_links(soup)
        )
        for item in items:
            title_el = item.select_one("h2, h3, h4, .title, .headline")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date, .release-date, .news-date")

            if item.name == "a":
                title = item.get_text(strip=True)
                href = item.get("href", "")
            elif title_el and link_el:
                title = title_el.get_text(strip=True)
                href = link_el["href"]
            else:
                continue

            if not title or len(title) < 10:
                continue

            url = href if href.startswith("http") else f"https://pr.tsmc.com{href}"
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
        if (len(text) > 20 and href not in seen
                and ("news" in href or "press" in href or is_soc_relevant(text))):
            seen.add(href)
            items.append(a)
    return items


def _parse_date_text(text: str) -> date:
    from datetime import datetime
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    TsmcCrawler().run()
