"""
summarize_sectors.py — 당일 수집분 섹터별 1문단 요약 + 상단 Top-5 (Phase 3, item 6·7)

입력 : raw_documents.crawled_at = 오늘(UTC) 인 건을 merge_log로 canonical_nodes에 매핑
       (noise 판정 제외, 같은 canonical로 병합된 건은 1건으로 집계)
LLM  : 전 섹터 1회 배치 호출 (헤드라인+요약만 투입 — 원문 전량 금지, 비용 가드)
랭킹 : Top-5는 휴리스틱만 사용 (LLM 미개입) — recency·source 신뢰·교차섹터 언급·watch trigger 매칭
       조합. 곱셈 인자가 0이면 전부 죽는 문제를 피하려고 recency×source를 base로,
       교차섹터/트리거는 ≥1.0 부스트로 적용 (지시서의 "×" 표기를 곱셈 그대로 구현하면
       트리거 불일치 항목이 전부 0점이 되어 상위 5 자체가 안 나올 수 있어 보정함).
출력 : data/refined/sector_summaries.json, data/refined/daily_top5.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db

_AXES = ["mobile_ap", "hpc_datacenter", "custom_soc", "foundry", "packaging"]
_MAX_ITEMS_PER_AXIS = 15  # 배치 호출 입력 상한 (비용 가드)

TAXONOMY_PATH = ROOT / "config" / "sector_taxonomy.json"
SECTOR_SUMMARIES_PATH = ROOT / "data" / "refined" / "sector_summaries.json"
TOP5_PATH = ROOT / "data" / "refined" / "daily_top5.json"

_PROMPT_TMPL = """\
You are a semiconductor competitive intelligence analyst writing a daily digest.

Below are today's collected headlines grouped by sector. For each sector listed,
write ONE paragraph (2-3 sentences) summarising the day's activity in that sector.

Rules (hard constraints):
- Base the summary ONLY on the headlines/summaries given below — do not invent facts.
- Do not include filler like "Today's headlines show".
- Be specific: technology, companies, capacity/roadmap moves.

{sections}
"""


def _load_taxonomy() -> dict:
    if not TAXONOMY_PATH.exists():
        return {"watch_triggers": []}
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def _fetch_today_items(conn) -> dict[str, list[dict]]:
    """오늘 crawled_at인 raw_documents → canonical_nodes 매핑, axis별 그룹화."""
    rows = conn.execute("""
        SELECT DISTINCT
            cn.id, cn.axis, cn.company, cn.title, cn.verification, cn.inference
        FROM raw_documents rd
        JOIN merge_log ml ON ml.raw_id = rd.id
        JOIN canonical_nodes cn ON ml.canonical_id = cn.id
        WHERE date(rd.crawled_at) = date('now')
          AND ml.decision != 'noise'
    """).fetchall()

    by_axis: dict[str, list[dict]] = {a: [] for a in _AXES}
    for row in rows:
        v = json.loads(row["verification"])
        inf = json.loads(row["inference"])
        item = {
            "axis": row["axis"],
            "company": row["company"],
            "headline": row["title"],
            "summary": inf.get("summary") or "",
            "tags": inf.get("tags") or [],
            "url": v.get("url") or "",
            "source": v.get("source") or "",
            "published_date": v.get("published_date") or "",
        }
        if item["axis"] in by_axis:
            by_axis[item["axis"]].append(item)
    return by_axis


def _generate_sector_summaries(by_axis: dict[str, list[dict]], client) -> dict:
    active = {a: items for a, items in by_axis.items() if items}
    if not active:
        return {}

    sections = []
    for axis, items in active.items():
        lines = "\n".join(
            f"- {it['headline']}" + (f" — {it['summary']}" if it["summary"] else "")
            for it in items[:_MAX_ITEMS_PER_AXIS]
        )
        sections.append(f"### {axis} ({len(items)} items)\n{lines}")

    tool_schema = {
        "name": "sector_summaries",
        "description": "One paragraph summary per sector",
        "input_schema": {
            "type": "object",
            "properties": {
                axis: {
                    "type": "string",
                    "description": f"2-3 sentence summary of today's {axis} sector activity",
                }
                for axis in active
            },
            "required": list(active.keys()),
            "additionalProperties": False,
        },
    }
    prompt = _PROMPT_TMPL.format(sections="\n\n".join(sections))

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": "sector_summaries"},
    )
    tool_block = next(b for b in resp.content if b.type == "tool_use")
    summaries: dict = tool_block.input

    now_ts = datetime.now(timezone.utc).isoformat()
    return {
        axis: {
            "summary": summaries.get(axis, ""),
            "item_count": len(items),
            "generated_at": now_ts,
        }
        for axis, items in active.items()
    }


def _recency_score(published_date: str) -> float:
    if not published_date:
        return 0.5
    try:
        days_ago = (date.today() - date.fromisoformat(published_date)).days
    except ValueError:
        return 0.5
    return max(0.2, 1.0 - min(days_ago, 3) / 3)


def _source_tier_score(source: str, preferred: list[str]) -> float:
    return 1.0 if any(p.lower() in (source or "").lower() for p in preferred) else 0.6


def _matches_trigger(text: str, triggers: list[dict]) -> bool:
    lower = text.lower()
    for trig in triggers:
        for kw in trig.get("recall_keywords", []):
            if kw.lower() in lower:
                return True
    return False


def _compute_top5(by_axis: dict[str, list[dict]], taxonomy: dict) -> list[dict]:
    all_items = [it for items in by_axis.values() for it in items]
    if not all_items:
        return []

    preferred = ["Reuters", "Bloomberg", "TechInsights", "SemiAnalysis", "DigiTimes", "TrendForce"]
    triggers = taxonomy.get("watch_triggers", [])

    # 교차섹터 언급수: 태그를 공유하는 서로 다른 axis 개수
    tag_to_axes: dict[str, set[str]] = {}
    for it in all_items:
        for tag in it["tags"]:
            tag_to_axes.setdefault(tag, set()).add(it["axis"])

    scored = []
    for it in all_items:
        cross_axes = set()
        for tag in it["tags"]:
            cross_axes |= tag_to_axes.get(tag, set())
        cross_count = max(1, len(cross_axes))  # 최소 1 (자기 자신)

        base = _recency_score(it["published_date"]) * _source_tier_score(it["source"], preferred)
        cross_boost = 1.0 + 0.15 * (cross_count - 1)
        text_for_trigger = f"{it['headline']} {it['summary']}"
        trigger_boost = 1.5 if _matches_trigger(text_for_trigger, triggers) else 1.0

        score = round(base * cross_boost * trigger_boost, 4)
        scored.append({
            **{k: it[k] for k in ("axis", "company", "headline", "url", "source", "published_date")},
            "score": score,
        })

    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:5]


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    init_db()
    conn = get_conn()
    try:
        by_axis = _fetch_today_items(conn)
    finally:
        conn.close()

    total = sum(len(v) for v in by_axis.values())
    print(f"[summarize_sectors] 오늘 수집분 {total}건 ({', '.join(f'{a}={len(v)}' for a, v in by_axis.items())})")

    taxonomy = _load_taxonomy()

    sector_summaries = {}
    if total and api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            sector_summaries = _generate_sector_summaries(by_axis, client)
        except Exception as exc:
            print(f"::warning::summarize_sectors sector summary generation failed: {exc}")
    elif total:
        print("::warning::ANTHROPIC_API_KEY not set — sector summaries skipped")

    top5 = _compute_top5(by_axis, taxonomy)

    now_ts = datetime.now(timezone.utc).isoformat()
    today_str = date.today().isoformat()

    SECTOR_SUMMARIES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECTOR_SUMMARIES_PATH.write_text(
        json.dumps({"date": today_str, "generated_at": now_ts, "sectors": sector_summaries},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    TOP5_PATH.write_text(
        json.dumps({"date": today_str, "generated_at": now_ts, "top5": top5},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[summarize_sectors] sectors={len(sector_summaries)} top5={len(top5)} → "
          f"{SECTOR_SUMMARIES_PATH.name}, {TOP5_PATH.name}")


if __name__ == "__main__":
    sys.exit(run())
