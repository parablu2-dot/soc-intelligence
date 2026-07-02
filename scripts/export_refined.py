"""
export_refined.py — canonical_nodes → data/refined/ RefinedSignal JSON

site/ 코드 수정 없음. canonical 데이터를 기존 RefinedSignal 스키마(100% 호환)로 변환·출력.
capacity_records.json은 crawlers/foundry/backfill_capacity.py가 별도 관리 — 덮어쓰지 않는다.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db

DATA_REFINED = ROOT / "data" / "refined"


def run() -> None:
    init_db()
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM canonical_nodes ORDER BY axis, company, updated_at DESC"
        ).fetchall()

        print(f"[export]  {len(rows)} canonical nodes found")
        if not rows:
            print("[export]  DB 비어 있음 — dedup_gate를 먼저 실행하세요")
            return

        # axis+company별로 그룹화
        by_axis_co: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for row in rows:
            r = dict(row)
            v = json.loads(r["verification"])
            inf = json.loads(r["inference"])

            # RefinedSignal 필수 필드
            signal: dict = {
                "axis": r["axis"],
                "company": r["company"],
                "category": v.get("category") or "news",
                "headline": r["title"],
                "url": v.get("url") or "",
                "published_date": v.get("published_date") or "",
                "source": v.get("source") or "",
            }
            # Optional 필드 — None이면 제외 (site/ 기존 동작 유지)
            if inf.get("tags"):
                signal["tags"] = inf["tags"]
            if inf.get("summary"):
                signal["summary"] = inf["summary"]

            by_axis_co[(r["axis"], r["company"])].append(signal)

        written = 0
        for (axis, company), signals in sorted(by_axis_co.items()):
            out_dir = DATA_REFINED / axis
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{company}.json"
            out_path.write_text(
                json.dumps(signals, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            written += 1
            print(f"  {axis}/{company}.json  ({len(signals)} signals)")

        print(f"[export]  {written} files written to data/refined/")

    finally:
        conn.close()


if __name__ == "__main__":
    run()
