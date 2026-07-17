"""
업체별 주요 전략 요약 백필 스크립트 (1회성 재검색).
20260717 작업지시서 항목 6 — 월간 전환에 앞서 최근 1년치 이력을 반영해 초기 요약을 재생성.

scripts/backfill_capacity.py와 동일하게 GitHub Actions에 등록하지 않는 수동 1회성 스크립트.
company_strategy.py의 generate_company_summaries()는 회사당 최근 10건만 보지만, 이 백필은
canonical_nodes 전체에서 최근 1년치 헤드라인을 모아 회사당 1회 LLM 호출로 요약한다
(비용 고려 — 회사당 여러 번 부르지 않음).

실행:
  cd soc-intelligence
  ANTHROPIC_API_KEY=... python scripts/backfill_company_strategy.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db
from scripts.company_strategy import generate_company_summaries

_LOOKBACK_DAYS = 365
_MAX_HEADLINES_PER_COMPANY = 40  # 1년치 전체가 아니라 상한을 둬 프롬프트 토큰을 통제


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("::warning::ANTHROPIC_API_KEY not set — backfill skipped")
        return

    import anthropic

    init_db()
    conn = get_conn()
    client = anthropic.Anthropic(api_key=api_key)
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=_LOOKBACK_DAYS)).isoformat()
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM canonical_nodes WHERE updated_at >= ?", (cutoff,)
        ).fetchone()["n"]
        print(f"[backfill_company_strategy] {count} canonical nodes within last {_LOOKBACK_DAYS} days")
        generate_company_summaries(
            conn, client, headlines_per_company=_MAX_HEADLINES_PER_COMPANY, since=cutoff
        )
    finally:
        conn.close()


if __name__ == "__main__":
    run()
