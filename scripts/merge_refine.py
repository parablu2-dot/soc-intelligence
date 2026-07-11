"""
merge_refine.py — LLM 병합 단계  ★ 프로젝트 내 유일한 LLM 호출 지점 ★

처리 대상 : merge_log.decision='merged' 이면서
            merge_log.decided_at > canonical_nodes.updated_at 인 건
            (= 이번 dedup_gate 실행에서 새로 생긴 merged 판정)

LLM 역할 : inference 필드(tags, summary)만 갱신 — 자유 재작성 금지
           verification 필드는 절대 출력 대상이 아님 (코드가 raw에서 직접 채움)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db, update_canonical

# ── 구조화 출력 스키마 ─────────────────────────────────────────────────────────
_TOOL_SCHEMA: dict = {
    "name": "update_inference",
    "description": "Update the inference fields for a canonical node after merging two signals",
    "input_schema": {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Merged, deduplicated tag list",
            },
            "summary": {
                "type": "string",
                "description": "Single concise sentence summarising both signals",
            },
        },
        "required": ["tags", "summary"],
        "additionalProperties": False,
    },
}

_PROMPT_TMPL = """\
You are a semiconductor competitive intelligence analyst.

Two signals about the same topic have been identified as near-duplicates.

Existing canonical title   : {existing_title}
Existing inference (current): {existing_inference}

New signal
  title  : {new_title}
  summary: {new_summary}
  tags   : {new_tags}

Call update_inference with:
  tags    — merged, deduplicated tag list (keep all relevant terms from both)
  summary — one concise sentence combining the key facts from both signals

Rules (hard constraints):
  - Do NOT invent facts absent from either signal.
  - Do NOT include company names, dates, or URLs in summary (those live in verification).
  - Do NOT rewrite the title.
"""


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("::warning::ANTHROPIC_API_KEY not set — LLM merge and company summaries skipped")
        return

    import anthropic

    init_db()
    conn = get_conn()
    client = anthropic.Anthropic(api_key=api_key)

    try:
        # merged 판정 중 canonical이 아직 갱신 안 된 건만 조회
        rows = conn.execute("""
            SELECT
                ml.raw_id, ml.canonical_id, ml.decided_at,
                rd.title        AS raw_title,
                rd.summary      AS raw_summary,
                rd.raw_json,
                cn.title        AS can_title,
                cn.inference,
                cn.updated_at   AS can_updated
            FROM merge_log ml
            JOIN raw_documents   rd ON ml.raw_id       = rd.id
            JOIN canonical_nodes cn ON ml.canonical_id = cn.id
            WHERE ml.decision = 'merged'
              AND ml.decided_at > cn.updated_at
        """).fetchall()

        print(f"[merge_refine] {len(rows)} merged decisions pending LLM update")
        if not rows:
            print("[merge_refine] no merged decisions — skipping merge step")
        else:
            now_ts = datetime.now(timezone.utc).isoformat()
            ok = fail = 0

            for row in rows:
                existing_inf = json.loads(row["inference"])
                raw_sig = json.loads(row["raw_json"])

                prompt = _PROMPT_TMPL.format(
                    existing_title=row["can_title"],
                    existing_inference=json.dumps(existing_inf, ensure_ascii=False),
                    new_title=row["raw_title"],
                    new_summary=row["raw_summary"] or "",
                    new_tags=json.dumps(raw_sig.get("tags") or [], ensure_ascii=False),
                )

                try:
                    resp = client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=256,
                        messages=[{"role": "user", "content": prompt}],
                        tools=[_TOOL_SCHEMA],
                        tool_choice={"type": "tool", "name": "update_inference"},
                    )
                    tool_block = next(b for b in resp.content if b.type == "tool_use")
                    new_inf: dict = tool_block.input
                    update_canonical(conn, row["canonical_id"], {
                        "inference": json.dumps(new_inf, ensure_ascii=False),
                        "updated_at": now_ts,
                    })
                    ok += 1
                except Exception as exc:
                    print(f"  [!] {row['canonical_id'][:10]}… error: {exc}")
                    fail += 1

            conn.commit()
            print(f"[merge_refine] done — ok={ok} fail={fail}")

        # merged 판정 유무와 무관하게 항상 회사별 요약 생성
        _generate_company_summaries(conn, client)

    finally:
        conn.close()


_SUMMARY_TOOL: dict = {
    "name": "company_summary",
    "description": "Generate a competitive intelligence summary for a semiconductor company in English, Simplified Chinese, and Korean",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary_en": {
                "type": "string",
                "description": "2-3 sentence competitive intelligence summary focusing on strategy, roadmap, and market position",
            },
            "summary_zh": {
                "type": "string",
                "description": "Faithful translation of summary_en into Simplified Chinese — same facts, no additions or omissions",
            },
            "summary_ko": {
                "type": "string",
                "description": "Faithful translation of summary_en into Korean — same facts, no additions or omissions",
            },
        },
        "required": ["summary_en", "summary_zh", "summary_ko"],
        "additionalProperties": False,
    },
}

_SUMMARY_PROMPT = """\
You are a semiconductor competitive intelligence analyst at SK hynix.

Company: {company}
Recent signals (newest first):
{headlines}

Write a 2-3 sentence competitive intelligence summary of this company's current strategic direction and market activity (summary_en).
Focus on technology roadmap, capacity moves, partnerships, and competitive positioning.
Do NOT include hiring news. Do NOT use filler phrases like "Based on recent signals".
Be concise and specific to observable facts.

Then provide the SAME summary faithfully translated into Simplified Chinese (summary_zh) and Korean (summary_ko).
Do not add or omit facts between language versions — they must convey identical information.
"""

_DATA_REFINED = ROOT / "data" / "refined"


def _generate_company_summaries(conn, client) -> None:
    """canonical_nodes를 회사별로 집계 → LLM 요약 → data/refined/company_summaries.json."""
    from collections import defaultdict

    rows = conn.execute(
        "SELECT company, title, updated_at FROM canonical_nodes "
        "WHERE company != 'hiring' "
        "ORDER BY updated_at DESC"
    ).fetchall()

    by_company: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if len(by_company[row["company"]]) < 10:
            by_company[row["company"]].append(row["title"])

    print(f"[company_summaries] {len(by_company)} companies to summarise")
    now_ts = datetime.now(timezone.utc).isoformat()
    summaries: dict = {}
    ok = fail = skip = 0

    for company, headlines in by_company.items():
        if len(headlines) < 2:
            skip += 1
            continue
        prompt = _SUMMARY_PROMPT.format(
            company=company,
            headlines="\n".join(f"- {h}" for h in headlines),
        )
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
                tools=[_SUMMARY_TOOL],
                tool_choice={"type": "tool", "name": "company_summary"},
            )
            tool_block = next(b for b in resp.content if b.type == "tool_use")
            summaries[company] = {
                "summary": tool_block.input["summary_en"],  # 하위호환 기본값 (구 프론트/캐시)
                "summary_en": tool_block.input["summary_en"],
                "summary_zh": tool_block.input.get("summary_zh", ""),  # A-2에서 ko/en로 재편, zh 유지 안 함
                "summary_ko": tool_block.input["summary_ko"],
                "signal_count": len(headlines),
                "generated_at": now_ts,
            }
            ok += 1
        except Exception as exc:
            print(f"::warning::company_summaries [{company}] failed: {exc}")
            fail += 1

    out = {
        "generated_at": now_ts,
        "summaries": summaries,
    }
    out_path = _DATA_REFINED / "company_summaries.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[company_summaries] ok={ok} fail={fail} skip={skip} → {out_path}")


if __name__ == "__main__":
    run()
