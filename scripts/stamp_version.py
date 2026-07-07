"""
stamp_version.py — data/refined/version.json의 "date" 필드만 빌드 시각으로 갱신.

version.json은 단일 진실원: version/maturity는 사람이 수동 편집, date만 이 스크립트가 build마다 자동 주입.
LLM 호출 없음 (runtime-token-zero 유지). 파일이 없으면 아무 것도 하지 않는다 (Phase 2에서 수동 생성됨).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "data" / "refined" / "version.json"


def run() -> None:
    if not VERSION_PATH.exists():
        print("[stamp_version] data/refined/version.json 없음 — 스킵")
        return

    data = json.loads(VERSION_PATH.read_text(encoding="utf-8"))
    data["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    VERSION_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[stamp_version] date → {data['date']} (version={data.get('version')})")


if __name__ == "__main__":
    sys.exit(run())
