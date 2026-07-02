"""
전자신문 반도체 뉴스 크롤러 (한국어 소스) — SoC/파운드리/공정 관련 기사 수집.
전자신문(ETNews)은 국내 최대 IT/전자 전문지로, 삼성·SK하이닉스·TSMC 한국어 보도에서 가장 빠름.

소스 1 (RSS): https://rss.etnews.com/Section901.xml  (반도체 섹션)
소스 2 (RSS 폴백): https://rss.etnews.com/Section902.xml  (전자 섹션)
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
    "https://rss.etnews.com/Section901.xml",  # 반도체
    "https://rss.etnews.com/Section902.xml",  # 전자
]
_SOURCE_NAME = "전자신문"

# 반도체 섹션은 대부분 SoC 관련이나, 너무 일반적인 기사를 제외하기 위한 필터
_KR_FILTER_KEYWORDS = [
    "반도체", "파운드리", "웨이퍼", "공정", "첨단패키징", "칩",
    "tsmc", "삼성 파운드리", "삼성파운드리", "인텔 파운드리",
    "엔비디아", "에이엠디", "퀄컴", "엑시노스", "미디어텍", "스냅드래곤",
    "hbm", "cowos", "chiplet", "2nm", "3nm", "4nm", "5nm",
    "시스템반도체", "메모리 반도체", "sk하이닉스", "삼성전자",
    "npu", "gpu", "ai칩", "ai 칩", "asic", "캐파", "수율",
]

# 언어 태그 — app.js의 KOREAN_SOURCES 기반 분류에 활용
_LANG_TAG = "KO"


class EtnewsCrawler(BaseCrawler):
    axis = "foundry"
    company = "etnews"

    def fetch(self) -> str:
        parts = []
        for url in _RSS_URLS:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                parts.append(f"### RSS_URL:{url} ###\n{resp.text}")
            except Exception as e:
                parts.append(f"### RSS_URL:{url} ### ERROR:{e}")
        return "\n\n".join(parts)

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        signals = []
        blocks = raw.split("### RSS_URL:")
        for block in blocks:
            if not block.strip():
                continue
            first_line, _, xml_body = block.partition(" ###\n")
            if "ERROR:" in xml_body:
                continue
            for item in parse_rss(xml_body):
                combined = f"{item['title']} {item['summary']}"
                if not self._is_relevant(combined):
                    continue
                tags = extract_tags(combined) or []
                if _LANG_TAG not in tags:
                    tags.append(_LANG_TAG)
                signals.append(RefinedSignal(
                    axis=self.axis,
                    company=self.company,
                    category=infer_category(combined),
                    headline=item["title"],
                    url=item["url"],
                    published_date=item["published_date"],
                    source=_SOURCE_NAME,
                    tags=tags if tags else None,
                    summary=item["summary"][:500] if item["summary"] else None,
                ))
        return signals

    def _is_relevant(self, text: str) -> bool:
        lower = text.lower()
        return (
            any(kw in lower for kw in _KR_FILTER_KEYWORDS)
            or is_soc_relevant(text)
        )


if __name__ == "__main__":
    EtnewsCrawler().run()
