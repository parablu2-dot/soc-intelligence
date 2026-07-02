"""
TrendForce 공개 뉴스 크롤러 — 파운드리 캐파, 웨이퍼 가격, 공정 노드 신호 수집.
TrendForce는 대만 시장 조사 기관으로, 공개 뉴스에서 TSMC/Samsung/SMIC 캐파 데이터를 가장 먼저 보도.

소스 1 (RSS 시도): https://www.trendforce.com/feed/
소스 2 (RSS 시도): https://press.trendforce.com/feed/
소스 3 (HTML 폴백): https://www.trendforce.com/news/
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, is_soc_relevant, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_RSS_URLS = [
    "https://www.trendforce.com/feed/",
    "https://press.trendforce.com/feed/",
]
_HTML_URL = "https://www.trendforce.com/news/"
_SOURCE_NAME = "TrendForce"

# TrendForce 특화 캐파/가격 키워드
_CAPACITY_KEYWORDS = [
    "capacity", "wafer", "foundry", "utilization", "fab", "node",
    "tsmc", "samsung", "smic", "globalfoundries", "intel foundry",
    "price", "shipment", "output", "production", "yield",
    "cowos", "hbm", "packaging", "chiplet", "3d ic",
    "2nm", "3nm", "4nm", "5nm", "advanced",
]


class TrendforceCrawler(BaseCrawler):
    axis = "foundry"
    company = "trendforce"

    def fetch(self) -> str:
        # RSS 시도
        for rss_url in _RSS_URLS:
            try:
                resp = requests.get(rss_url, headers=HEADERS, timeout=30)
                if resp.ok and ("<rss" in resp.text[:500] or "<feed" in resp.text[:500]):
                    return resp.text
            except Exception:
                continue
        # HTML 폴백
        try:
            resp = requests.get(_HTML_URL, headers=HEADERS, timeout=30)
            if resp.ok:
                return resp.text
        except Exception:
            pass
        return ""

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        if "<rss" in raw[:500] or "<feed" in raw[:500]:
            return self._parse_rss(raw)
        return self._parse_html(raw)

    def _parse_rss(self, raw: str) -> list[RefinedSignal]:
        signals = []
        for item in parse_rss(raw):
            title = _clean_headline(item["title"])
            combined = f"{title} {item['summary']}"
            if not self._is_relevant(combined):
                continue
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(combined),
                headline=title,
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
            soup.select(".news-list li, .news-item, article.post")
            or soup.select(".entry-title a")
            or _fallback_links(soup)
        )
        for item in items:
            # 링크 태그 직접 처리
            if item.name == "a":
                title = _clean_headline(item.get_text(strip=True))
                href = item.get("href", "")
            else:
                title_el = item.select_one("h2 a, h3 a, h4 a, .title a, a.news-title")
                if not title_el:
                    title_el = item.select_one("a[href]")
                if not title_el:
                    continue
                title = _clean_headline(title_el.get_text(strip=True))
                href = title_el.get("href", "")

            if not title or len(title) < 10:
                continue
            if not self._is_relevant(title):
                continue

            url = href if href.startswith("http") else f"https://www.trendforce.com{href}"
            date_el = item.select_one("time, .date, .post-date, .publish-date")
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

    def _is_relevant(self, text: str) -> bool:
        lower = text.lower()
        return any(kw in lower for kw in _CAPACITY_KEYWORDS) or is_soc_relevant(text)


import re as _re

def _clean_headline(title: str) -> str:
    """[News], [Insights], [Report] 등 섹션 접두사 제거."""
    return _re.sub(r'^\s*\[[\w\s]+\]\s*', '', title).strip()


def _fallback_links(soup: BeautifulSoup) -> list:
    seen = set()
    items = []
    for a in soup.find_all("a", href=True):
        text = a.get_text(strip=True)
        href = a["href"]
        if (len(text) > 20 and href not in seen
                and ("news" in href or "press" in href or "report" in href)):
            seen.add(href)
            items.append(a)
    return items[:50]


def _parse_date_text(text: str) -> date:
    from datetime import datetime
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%Y/%m/%d", "%d %B %Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    TrendforceCrawler().run()
