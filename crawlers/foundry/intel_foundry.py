"""
Intel Foundry (IFS) 뉴스 크롤러 — Intel 18A/3/4/7 공정, 외부 고객 수주 신호 수집.
소스: Intel 뉴스룸 RSS/HTML에서 IFS 키워드 필터링
"""
from datetime import date

import requests
from bs4 import BeautifulSoup

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, extract_tags, infer_category
)
from crawlers.common.schema import RefinedSignal

_RSS_URLS = [
    "https://newsroom.intel.com/feed/",
    "https://www.intel.com/content/www/us/en/newsroom/news/press-rss.html",
]
_HTML_URL = "https://newsroom.intel.com/news"
_SOURCE_NAME = "Intel Newsroom"

_IFS_KEYWORDS = [
    "intel foundry", "ifs", "foundry services", "18a", "intel 3", "intel 4",
    "intel 7", "intel 20a", "angstrom", "1.8a", "foundry", "wafer", "fab",
    "manufacturing process", "external customer", "process node",
]


def _is_ifs_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _IFS_KEYWORDS)


class IntelFoundryCrawler(BaseCrawler):
    axis = "foundry"
    company = "intel_foundry"

    def fetch(self) -> str:
        for rss_url in _RSS_URLS:
            try:
                resp = requests.get(rss_url, headers=HEADERS, timeout=30)
                if resp.ok and ("<rss" in resp.text[:500] or "<feed" in resp.text[:500]):
                    return resp.text
            except Exception:
                continue
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
        if raw.strip().startswith("<?xml") or "<rss" in raw[:500] or "<feed" in raw[:500]:
            return self._parse_rss(raw)
        return self._parse_html(raw)

    def _parse_rss(self, raw: str) -> list[RefinedSignal]:
        signals = []
        for item in parse_rss(raw):
            combined = f"{item['title']} {item['summary']}"
            if not _is_ifs_relevant(combined):
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
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            if len(text) > 20 and _is_ifs_relevant(text):
                href = a["href"]
                url = href if href.startswith("http") else f"https://newsroom.intel.com{href}"
                signals.append(RefinedSignal(
                    axis=self.axis,
                    company=self.company,
                    category=infer_category(text),
                    headline=text,
                    url=url,
                    published_date=date.today(),
                    source=_SOURCE_NAME,
                    tags=extract_tags(text),
                    summary=None,
                ))
        return signals


if __name__ == "__main__":
    IntelFoundryCrawler().run()
