#!/usr/bin/env python3
"""
process_axis_change.py — 구독 축 변경 토큰 처리 (2026-08-30, process_unsubscribe.py와 동일 패턴).

설계 원칙 (process_unsubscribe.py 그대로 계승):
- 이메일 "구독 축 변경" 링크는 mailto:(SMTP_USER, subject에 토큰 포함)로만 구성 — 자동 처리
  백엔드는 만들지 않는다(1~2고객 규모에서 과설계, unsubscribe와 동일한 YAGNI 판단).
- 운영자가 메일로 받은 토큰+원하는 축 목록을 이 CLI(또는 동명 workflow_dispatch)에 입력하면
  실제로 검증 후 data/subscribers/subscribers.json의 해당 항목 axes를 갱신·커밋한다.
- unsubscribe_token을 그대로 재사용한다(별도 change_token 신설 안 함) — 토큰 하나로 해지/변경
  둘 다 식별 가능하면 충분하고, 토큰 종류를 늘리면 메일 템플릿·시크릿 관리가 늘어남.

사용법:
    python scripts/process_axis_change.py --token <token> --axes hpc_datacenter,packaging,pmic
    python scripts/process_axis_change.py --list-axes   # 선택 가능한 축 목록 확인
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUBSCRIBERS_PATH = ROOT / "data" / "subscribers" / "subscribers.json"

from scripts.subscriber_schema import AXES_ACTIVE  # 일간 발송이 실제로 콘텐츠를 가진 축 목록


def _load() -> list[dict]:
    if not SUBSCRIBERS_PATH.exists():
        return []
    return json.loads(SUBSCRIBERS_PATH.read_text(encoding="utf-8"))


def _save(subscribers: list[dict]) -> None:
    SUBSCRIBERS_PATH.write_text(
        json.dumps(subscribers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def process_token(token: str, axes: list[str]) -> str:
    """토큰을 검증하고 매칭 구독자의 axes를 갱신한다. 결과 메시지를 반환한다."""
    invalid = [a for a in axes if a not in AXES_ACTIVE]
    if invalid:
        return f"알 수 없는 축: {invalid} (선택 가능: {AXES_ACTIVE})"
    if not axes:
        return "축을 최소 1개 이상 지정해야 합니다"

    subscribers = _load()
    for sub in subscribers:
        if sub.get("unsubscribe_token") == token:
            old_axes = sub.get("axes") or []
            sub["axes"] = axes
            sub["axes_changed_at"] = datetime.now(timezone.utc).isoformat()
            _save(subscribers)
            return (f"축 변경 완료: customer_id={sub['customer_id']} "
                    f"{old_axes} -> {axes}")
    return "일치하는 토큰을 찾지 못했습니다 (이미 처리됐거나 잘못된 토큰일 수 있음)"


def cli():
    parser = argparse.ArgumentParser(description="구독 축 변경 토큰 처리")
    parser.add_argument("--token", help="구독 축 변경 요청 메일에 담긴 unsubscribe_token")
    parser.add_argument("--axes", help="콤마로 구분된 축 목록 (예: hpc_datacenter,packaging,pmic)")
    parser.add_argument("--list-axes", action="store_true", help="선택 가능한 축 목록 출력")
    args = parser.parse_args()

    if args.list_axes:
        print(", ".join(AXES_ACTIVE))
        return

    if not args.token or not args.axes:
        parser.error("--token과 --axes 둘 다 필요합니다 (또는 --list-axes)")

    axes = [a.strip() for a in args.axes.split(",") if a.strip()]
    print(process_token(args.token, axes))


if __name__ == "__main__":
    sys.exit(cli())
