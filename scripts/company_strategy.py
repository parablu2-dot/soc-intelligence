"""
company_strategy.py — 업체별 주요 전략(LLM 요약) 생성. 월 1회 실행(company-strategy.yml).

기존 merge_refine.py의 _generate_company_summaries()를 그대로 분리한 것.
daily crawl-and-build.yml에서는 더 이상 호출하지 않는다(비용/변경빈도 고려 —
회사 전략 요약은 하루하루 바뀌지 않으므로 매일 재생성할 이유가 없다).

실행:
  cd soc-intelligence
  ANTHROPIC_API_KEY=... python scripts/company_strategy.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db

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


def generate_company_summaries(conn, client, *, headlines_per_company: int = 10, since: str | None = None) -> None:
    """canonical_nodes를 회사별로 집계 → LLM 요약 → data/refined/company_summaries.json.

    since: ISO timestamp. 지정하면 그 이후 updated_at인 노드만 대상으로 함(백필의 lookback window).
    """
    if since:
        rows = conn.execute(
            "SELECT company, title, updated_at FROM canonical_nodes "
            "WHERE company != 'hiring' AND updated_at >= ? "
            "ORDER BY updated_at DESC",
            (since,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT company, title, updated_at FROM canonical_nodes "
            "WHERE company != 'hiring' "
            "ORDER BY updated_at DESC"
        ).fetchall()

    by_company: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if len(by_company[row["company"]]) < headlines_per_company:
            by_company[row["company"]].append(row["title"])

    print(f"[company_strategy] {len(by_company)} companies to summarise")
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
                max_tokens=768,  # 3개 언어(en/zh/ko) 요약 전체를 담기엔 256이 부족해 응답이 잘려 필드가 누락되던 근본 원인
                messages=[{"role": "user", "content": prompt}],
                tools=[_SUMMARY_TOOL],
                tool_choice={"type": "tool", "name": "company_summary"},
            )
            tool_block = next(b for b in resp.content if b.type == "tool_use")
            summaries[company] = {
                "summary": tool_block.input.get("summary_en", ""),  # 하위호환 기본값 (구 프론트/캐시)
                "summary_en": tool_block.input.get("summary_en", ""),
                "summary_zh": tool_block.input.get("summary_zh", ""),
                "summary_ko": tool_block.input.get("summary_ko", ""),
                "signal_count": len(headlines),
                "generated_at": now_ts,
            }
            ok += 1
        except Exception as exc:
            print(f"::warning::company_strategy [{company}] failed: {exc}")
            fail += 1

    out = {
        "generated_at": now_ts,
        "summaries": summaries,
    }
    out_path = _DATA_REFINED / "company_summaries.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[company_strategy] ok={ok} fail={fail} skip={skip} → {out_path}")


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("::warning::ANTHROPIC_API_KEY not set — company strategy summaries skipped")
        return

    import anthropic

    init_db()
    conn = get_conn()
    client = anthropic.Anthropic(api_key=api_key)
    try:
        generate_company_summaries(conn, client)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
