"""
MediaTek 뉴스룸 HTML 크롤러 — Dimensity / 모바일 AP 관련 신호 수집.
소스: https://www.mediatek.com/news-events/news
"""
from datetime import date

from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    fetch_html, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_SOURCE_URL = "https://www.mediatek.com/blog"
_SOURCE_NAME = "MediaTek Newsroom"


class MediaTekCrawler(BaseCrawler):
    axis = "mobile_ap"
    company = "mediatek"

    def fetch(self) -> str:
        return fetch_html(_SOURCE_URL)

    def parse(self, raw: str) -> list[RefinedSignal]:
        soup = BeautifulSoup(raw, "lxml")
        signals = []

        # MediaTek 뉴스룸 — 기사 카드 셀렉터 (구조 변경 시 갱신 필요)
        items = (
            soup.select(".news-list__item")
            or soup.select("article")
            or soup.select(".card")
            or _fallback_links(soup)
        )

        for item in items:
            title_el = item.select_one("h2, h3, h4, .card__title, .news-title")
            link_el = item.select_one("a[href]")
            date_el = item.select_one("time, .date, .card__date")

            if not title_el or not link_el:
                continue

            title = title_el.get_text(strip=True)
            href = link_el["href"]
            base_domain = "https://www.mediatek.com"
            url = href if href.startswith("http") else f"{base_domain}{href}"
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
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    MediaTekCrawler().run()
