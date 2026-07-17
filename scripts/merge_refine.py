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

        # 업체별 전략 요약(company_summaries.json)은 scripts/company_strategy.py로 분리,
        # company-strategy.yml에서 월 1회 별도 실행 (daily 재생성 불필요 — Phase 6, 20260717)

    finally:
        conn.close()


if __name__ == "__main__":
    run()
