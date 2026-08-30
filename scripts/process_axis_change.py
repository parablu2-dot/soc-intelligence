#!/usr/bin/env python3
"""
process_axis_change.py — 구독 설정(축·수신 요일) 변경 토큰 처리 (2026-08-30, process_unsubscribe.py
와 동일 패턴; 2026-08-30 추가 요청으로 축뿐 아니라 delivery_days도 같이 처리하도록 확장).

설계 원칙 (process_unsubscribe.py 그대로 계승):
- 이메일 "구독 설정 변경" 링크는 mailto:(SMTP_USER, subject에 토큰 포함)로만 구성 — 자동 처리
  백엔드는 만들지 않는다(1~2고객 규모에서 과설계, unsubscribe와 동일한 YAGNI 판단).
- 운영자가 메일로 받은 토큰+원하는 값을 이 CLI(또는 동명 workflow_dispatch)에 입력하면 실제로
  검증 후 data/subscribers/subscribers.json의 해당 항목을 갱신·커밋한다.
- unsubscribe_token을 그대로 재사용한다(별도 change_token 신설 안 함) — 토큰 하나로 해지/변경
  둘 다 식별 가능하면 충분하고, 토큰 종류를 늘리면 메일 템플릿·시크릿 관리가 늘어남.
- --axes/--days는 각각 독립 — 하나만 줘도 되고 둘 다 줘도 된다(둘 다 생략하면 에러).

사용법:
    python scripts/process_axis_change.py --token <token> --axes hpc_datacenter,packaging,pmic
    python scripts/process_axis_change.py --token <token> --days mon,wed,fri
    python scripts/process_axis_change.py --token <token> --axes pmic --days mon,fri
    python scripts/process_axis_change.py --list-axes   # 선택 가능한 축/요일 목록 확인
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SUBSCRIBERS_PATH = ROOT / "data" / "subscribers" / "subscribers.json"

from scripts.subscriber_schema import AXES_ACTIVE, DELIVERY_DAYS  # 선택 가능한 값들의 단일 소스


def _load() -> list[dict]:
    if not SUBSCRIBERS_PATH.exists():
        return []
    return json.loads(SUBSCRIBERS_PATH.read_text(encoding="utf-8"))


def _save(subscribers: list[dict]) -> None:
    SUBSCRIBERS_PATH.write_text(
        json.dumps(subscribers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def process_token(token: str, axes: list[str] | None = None, days: list[str] | None = None) -> str:
    """토큰을 검증하고 매칭 구독자의 axes/delivery_days를 갱신한다. 결과 메시지를 반환한다.
    axes/days 둘 다 None이면 아무것도 안 바꾸는 게 아니라 호출자 실수이므로 에러로 취급한다."""
    if axes is None and days is None:
        return "axes 또는 days 중 최소 하나는 지정해야 합니다"
    if axes is not None:
        invalid_axes = [a for a in axes if a not in AXES_ACTIVE]
        if invalid_axes:
            return f"알 수 없는 축: {invalid_axes} (선택 가능: {AXES_ACTIVE})"
        if not axes:
            return "axes를 지정하려면 최소 1개 이상이어야 합니다"
    if days is not None:
        invalid_days = [d for d in days if d not in DELIVERY_DAYS]
        if invalid_days:
            return f"알 수 없는 요일: {invalid_days} (선택 가능: {DELIVERY_DAYS})"
        if not days:
            return "days를 지정하려면 최소 1개 이상이어야 합니다"

    subscribers = _load()
    for sub in subscribers:
        if sub.get("unsubscribe_token") == token:
            changes = []
            if axes is not None:
                old_axes = sub.get("axes") or []
                sub["axes"] = axes
                changes.append(f"axes {old_axes} -> {axes}")
            if days is not None:
                old_days = sub.get("delivery_days") or "기본값(평일 전체)"
                sub["delivery_days"] = days
                changes.append(f"delivery_days {old_days} -> {days}")
            sub["settings_changed_at"] = datetime.now(timezone.utc).isoformat()
            _save(subscribers)
            return f"변경 완료: customer_id={sub['customer_id']} — " + "; ".join(changes)
    return "일치하는 토큰을 찾지 못했습니다 (이미 처리됐거나 잘못된 토큰일 수 있음)"


def cli():
    parser = argparse.ArgumentParser(description="구독 설정(축·수신 요일) 변경 토큰 처리")
    parser.add_argument("--token", help="구독 설정 변경 요청 메일에 담긴 unsubscribe_token")
    parser.add_argument("--axes", help="콤마로 구분된 축 목록 (예: hpc_datacenter,packaging,pmic)")
    parser.add_argument("--days", help="콤마로 구분된 수신 요일 목록 (예: mon,wed,fri)")
    parser.add_argument("--list-axes", action="store_true", help="선택 가능한 축/요일 목록 출력")
    args = parser.parse_args()

    if args.list_axes:
        print("축:", ", ".join(AXES_ACTIVE))
        print("요일:", ", ".join(DELIVERY_DAYS))
        return

    if not args.token or (not args.axes and not args.days):
        parser.error("--token과 (--axes 또는 --days) 중 최소 하나가 필요합니다 (또는 --list-axes)")

    axes = [a.strip() for a in args.axes.split(",") if a.strip()] if args.axes else None
    days = [d.strip().lower() for d in args.days.split(",") if d.strip()] if args.days else None
    print(process_token(args.token, axes, days))


if __name__ == "__main__":
    sys.exit(cli())
