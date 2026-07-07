"""
googlenews_axis.py — 축별 Google News RSS 크롤러 공통 베이스 (Phase 4, item 2).

hiring.py가 이미 config.yaml의 hiring_targets에서 쿼리를 로드하는 선례를 따름 —
새 sources.yaml을 만들지 않고 config.yaml의 axis_news_queries에 얹는다.
QUERY는 Phase 1 config/sector_taxonomy.json에서 축별로 추출해 axis_news_queries에 미리 적재해둠.

가드 (aggregator 특성상 중복·저품질 많음):
  - source_tier="aggregator" 태깅 — dedup_gate.py/summarize_sectors.py가 신뢰도 구분에 사용
  - dedupe_by_title()로 크롤러 단계에서 동일 기사 중복 완화 (dedup_gate.py의 axis+company
    스코프 임베딩 dedup과는 별개 — company='googlenews'라 기존 개별 크롤러(tsmc 등)와는
    dedup_gate에서 병합되지 않음. 이는 entities_match()의 company 일치 요구를 그대로 둔 것으로,
    cross-company 병합 허용은 전체 파이프라인의 false-merge 방지 원칙을 건드리는 별도 검토 사안)
  - is_soc_relevant()로 축별 쿼리에도 섞여드는 무관 결과 필터링
"""
import urllib.parse
from pathlib import Path

import requests
import yaml

from crawlers.common.base_crawler import BaseCrawler
from crawlers.common.rss_utils import (
    HEADERS, parse_rss, is_soc_relevant, extract_tags, infer_category, dedupe_by_title,
)
from crawlers.common.schema import RefinedSignal

_CFG_PATH = Path(__file__).resolve().parents[2] / "crawlers" / "config.yaml"


def _load_query(axis: str) -> str:
    cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    queries: dict = cfg.get("axis_news_queries", {})
    return queries.get(axis, "")


class GoogleNewsAxisCrawler(BaseCrawler):
    """축별 하위 클래스는 axis 클래스 속성만 지정하면 된다 (company는 'googlenews' 고정)."""
    company = "googlenews"

    def fetch(self) -> str:
        query = _load_query(self.axis)
        if not query:
            return ""
        encoded = urllib.parse.quote(query)
        url = (
            f"https://news.google.com/rss/search"
            f"?q={encoded}+when:1d&hl=en-US&gl=US&ceid=US:en"
        )
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.text

    def parse(self, raw: str) -> list[RefinedSignal]:
        if not raw:
            return []
        items = dedupe_by_title(parse_rss(raw))
        signals = []
        for item in items:
            full = f"{item['title']} {item['summary']}"
            if not is_soc_relevant(full):
                continue
            signals.append(RefinedSignal(
                axis=self.axis,
                company=self.company,
                category=infer_category(full),
                headline=item["title"],
                url=item["url"],
                published_date=item["published_date"],
                source="Google News",
                tags=extract_tags(full) or None,
                summary=item["summary"][:500] if item["summary"] else None,
                source_tier="aggregator",
            ))
        return signals
