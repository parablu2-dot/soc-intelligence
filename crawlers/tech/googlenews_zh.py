"""
crawlers/tech/googlenews_zh.py — 중국어권(zh) 뉴스 소스 (20260717 후속 작업지시서, 항목 4 대안).

Baidu 뉴스/검색은 robots.txt 전면 차단 + 공식 API 없음으로 불가 판정
(docs/zh-source-feasibility-20260717.md 참고). 대안으로 이미 프로젝트에 있는
Google News RSS 패턴(crawlers/common/googlenews_axis.py)을 hl=zh-CN/gl=CN/ceid=CN:zh로
변형해 사용한다.

arxiv.py와 동일하게 TechSignal(axis/company 없음)로 저장 — 이 zh 뉴스는 5축 경쟁사
추적과는 별개로 "중국어권에서 SoC 도메인이 어떻게 보도되는가"를 보는 별도 stratum이다.
dedup_gate/merge_refine을 거치지 않고 URL 기준 누적만 한다(LLM 미개입, 결정론적).

저장: data/refined/tech/news_zh.json (누적 — 기존 항목 유지, 신규만 추가)
"""
from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from crawlers.common.rss_utils import HEADERS, parse_rss, is_soc_relevant, dedupe_by_title
from crawlers.common.schema import TechSignal

_CFG_PATH = ROOT / "crawlers" / "config.yaml"
OUT_PATH = ROOT / "data" / "refined" / "tech" / "news_zh.json"


def _load_query() -> str:
    cfg = yaml.safe_load(_CFG_PATH.read_text(encoding="utf-8"))
    return cfg.get("tech_zh_query", "")


def fetch() -> str:
    query = _load_query()
    if not query:
        return ""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}+when:1d&hl=zh-CN&gl=CN&ceid=CN:zh"
    )
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse(raw: str) -> list[TechSignal]:
    if not raw:
        return []
    items = dedupe_by_title(parse_rss(raw))
    signals = []
    for item in items:
        full = f"{item['title']} {item['summary']}"
        if not is_soc_relevant(full):
            continue
        signals.append(TechSignal(
            lens="tech",
            source_class="news",
            category="zh_news",
            title=item["title"],
            url=item["url"],
            published_date=str(item["published_date"]),  # parse_rss는 date 객체 반환 → "YYYY-MM-DD" 문자열로 고정
            source="Google News (zh)",
            summary=item["summary"][:500] if item["summary"] else None,
        ))
    return signals


def _load_existing() -> list[dict]:
    if not OUT_PATH.exists():
        return []
    import json
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def run() -> None:
    import json

    raw = fetch()
    new_signals = parse(raw)

    existing = _load_existing()
    seen_urls = {rec["url"] for rec in existing if rec.get("url")}

    added = 0
    for sig in new_signals:
        if sig.url in seen_urls:
            continue
        existing.append(sig.to_dict())
        seen_urls.add(sig.url)
        added += 1

    existing.sort(key=lambda r: r.get("published_date", ""), reverse=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[googlenews_zh] fetched={len(new_signals)} added={added} total={len(existing)} → {OUT_PATH}")


if __name__ == "__main__":
    run()
