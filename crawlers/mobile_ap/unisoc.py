"""
Unisoc 뉴스 HTML 크롤러 — 엔트리/미드레인지 AP 관련 신호 수집.
소스: https://www.unisoc.com/en_us/news
"""
from datetime import date

from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    fetch_html, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_SOURCE_URL = "https://www.unisoc.com/en_us/news"
_SOURCE_NAME = "Unisoc"


class UnisocCrawler(BaseCrawler):
    axis = "mobile_ap"
    company = "unisoc"

    def fetch(self) -> str:
        return fetch_html(_SOURCE_URL)

    def parse(self, raw: str) -> list[RefinedSignal]:
        soup = BeautifulSoup(raw, "lxml")
        signals = []

        # Unisoc 뉴스 — 셀렉터 (구조 변경 시 갱신 필요)
        items = (
            soup.select(".news-list li")
            or soup.select("article")
            or soup.select(".news-item")
            or _fallback_links(soup, base="https://www.unisoc.com")
        )

        for item in items:
            if isinstance(item, str):
                continue
            title_el = item.select_one("h2, h3, h4, .title, p.news-title")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, span.date, .time")

            if not title_el or not link_el:
                # fallback_links 모드에서는 item 자체가 <a>
                if item.name == "a":
                    title = item.get_text(strip=True)
                    href = item.get("href", "")
                    url = href if href.startswith("http") else f"https://www.unisoc.com{href}"
                else:
                    continue
            else:
                title = title_el.get_text(strip=True)
                href = link_el["href"]
                url = href if href.startswith("http") else f"https://www.unisoc.com{href}"

            pub_date = _parse_date_text(date_el.get_text(strip=True) if date_el else "")

            combined = title
            if not is_soc_relevant(combined):
                continue

            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(combined),
                headline=title,
                url=url,
                published_date=pub_date,
                source=_SOURCE_NAME,
                tags=extract_tags(combined),
                summary=None,
            ))

        return signals


def _fallback_links(soup: BeautifulSoup, base: str = "") -> list:
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
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    UnisocCrawler().run()
