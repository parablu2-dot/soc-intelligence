"""
crawlers/tech/arxiv.py — arXiv 논문 소스 (Phase 5, item 3).

뉴스 크롤러(BaseCrawler, axis/company 기반)와는 다른 별도 source class.
저volocity·고신호 stratum이므로 dedup_gate/merge_refine 파이프라인을 거치지 않고
arXiv abs URL(전역 고유) 기준으로 누적만 한다 — LLM 미개입, 결정론적.

저장: data/refined/tech/papers.json (누적 — 기존 항목 유지, 신규만 추가)
dedup_gate.py는 data/refined/tech/ 를 ingestion에서 제외한다 (capacity_records.json과 동일 취급).
"""
from __future__ import annotations

import sys
from pathlib import Path

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from crawlers.common.rss_utils import HEADERS, is_soc_relevant, strip_html
from crawlers.common.schema import TechSignal

# cat: cs.AR(컴퓨터 아키텍처), eess.SP(신호처리), cond-mat.mtrl-sci(재료과학), physics.app-ph(응용물리)
_CATEGORIES = ["cs.AR", "eess.SP", "cond-mat.mtrl-sci", "physics.app-ph"]
_API_URL = (
    "http://export.arxiv.org/api/query"
    "?search_query=" + "+OR+".join(f"cat:{c}" for c in _CATEGORIES) +
    "&sortBy=submittedDate&sortOrder=descending&max_results=50"
)

OUT_PATH = ROOT / "data" / "refined" / "tech" / "papers.json"


def fetch() -> str:
    resp = requests.get(_API_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse(raw: str) -> list[TechSignal]:
    feed = feedparser.parse(raw)
    signals = []
    for entry in feed.entries:
        title = strip_html(entry.get("title", "")).replace("\n", " ").strip()
        summary = strip_html(entry.get("summary", ""))
        full = f"{title} {summary}"
        if not is_soc_relevant(full):
            continue

        category = entry.get("arxiv_primary_category", {}).get("term") or (
            entry.tags[0]["term"] if entry.get("tags") else ""
        )
        authors = [a.get("name", "") for a in entry.get("authors", [])] or None
        published = entry.get("published", "")[:10]  # "YYYY-MM-DD"

        signals.append(TechSignal(
            lens="tech",
            source_class="paper",
            category=category,
            title=title,
            url=entry.get("link", ""),
            published_date=published,
            source="arXiv",
            summary=summary[:500] if summary else None,
            authors=authors,
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
    print(f"[arxiv] fetched={len(new_signals)} added={added} total={len(existing)} → {OUT_PATH}")


if __name__ == "__main__":
    run()
