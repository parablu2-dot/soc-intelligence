"""
SMIC(中芯国际) 영문 뉴스 크롤러 — 중국 파운드리 공정 개발 신호 수집.
소스 (HTML): https://www.smics.com/en/site/news_company
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_NEWS_URL = "https://www.smics.com/en/site/news_company"
_SOURCE_NAME = "SMIC"


class SmicCrawler(BaseCrawler):
    axis = "foundry"
    company = "smic"

    def fetch(self) -> str:
        try:
            resp = requests.get(_NEWS_URL, headers=HEADERS, timeout=30)
            if resp.ok:
                return resp.text
        except Exception:
            pass
        return ""

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        soup = BeautifulSoup(raw, "lxml")
        signals = []
        items = (
            soup.select(".news-list li, .news-item, article")
            or _fallback_links(soup)
        )
        for item in items:
            title_el = item.select_one("h2, h3, h4, .title, a")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date, .news-date, span")

            if item.name == "a":
                title, href = item.get_text(strip=True), item.get("href", "")
            elif title_el and link_el:
                title, href = title_el.get_text(strip=True), link_el["href"]
            else:
                continue

            if not title or len(title) < 10:
                continue

            url = href if href.startswith("http") else f"https://www.smics.com{href}"
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
        if len(text) > 15 and ("news" in href or "press" in href) and href not in seen:
            seen.add(href)
            items.append(a)
    return items


def _parse_date_text(text: str) -> date:
    from datetime import datetime
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    SmicCrawler().run()
