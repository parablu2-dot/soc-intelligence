#!/usr/bin/env python3
"""
add_subscriber.py — 신규 구독자 등록 (2026-08-30, process_unsubscribe.py/process_axis_change.py와
같은 계열의 subscribers.json 조작 CLI).

과거 실수 재발 방지 목적으로 신설: 첫 CPO 고객 등록 때 customer_id 자리에 플레이스홀더 문자열
"customer_id"를 그대로 써버린 적이 있었음(수동 JSON 편집의 전형적인 실수). 이 스크립트는:
  - customer_id 중복 검사
  - axes/schedule/days 값 검증 (process_axis_change.py와 동일 소스, subscriber_schema.py)
  - unsubscribe_token을 手동 입력이 아니라 secrets.token_urlsafe()로 항상 새로 생성
    (토큰 재사용/추측 가능한 값 방지)
을 강제해 사람이 직접 JSON을 편집할 때 나던 실수 종류를 원천 차단한다.

**이메일은 여기서 다루지 않는다** — subscribers.json은 public repo에 커밋되므로 PII(이메일) X.
이 스크립트 실행 후 화면에 나오는 안내대로 GitHub repo secret(CPO_SUBSCRIBER_EMAILS)에
{customer_id: email} 쌍을 수동으로 추가해야 실제 발송이 된다.

사용법:
    python scripts/add_subscriber.py --customer-id acme-corp --axes hpc_datacenter,packaging
    python scripts/add_subscriber.py --customer-id acme-corp --axes pmic --days mon,wed,fri
    python scripts/add_subscriber.py --list   # 현재 구독자 목록 (PII 없음)
"""
import argparse
import json
import secrets
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.subscriber_schema import AXES_ACTIVE, DELIVERY_DAYS

SUBSCRIBERS_PATH = ROOT / "data" / "subscribers" / "subscribers.json"


def _load() -> list[dict]:
    if not SUBSCRIBERS_PATH.exists():
        return []
    return json.loads(SUBSCRIBERS_PATH.read_text(encoding="utf-8"))


def _save(subscribers: list[dict]) -> None:
    SUBSCRIBERS_PATH.write_text(
        json.dumps(subscribers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def add_subscriber(customer_id: str, axes: list[str], schedule: str = "weekday",
                    days: list[str] | None = None) -> str:
    if not customer_id or customer_id.strip() != customer_id:
        return "customer_id가 비어있거나 앞뒤 공백이 있습니다"
    if customer_id == "customer_id":
        return "customer_id로 문자 그대로 'customer_id'를 쓸 수 없습니다 (과거 실수 재발 방지) — 실제 식별자를 입력하세요"

    invalid_axes = [a for a in axes if a not in AXES_ACTIVE]
    if invalid_axes:
        return f"알 수 없는 축: {invalid_axes} (선택 가능: {AXES_ACTIVE})"
    if not axes:
        return "axes를 최소 1개 이상 지정해야 합니다"

    if days:
        invalid_days = [d for d in days if d not in DELIVERY_DAYS]
        if invalid_days:
            return f"알 수 없는 요일: {invalid_days} (선택 가능: {DELIVERY_DAYS})"

    subscribers = _load()
    if any(s.get("customer_id") == customer_id for s in subscribers):
        return f"이미 존재하는 customer_id입니다: {customer_id}"

    token = secrets.token_urlsafe(24)
    record = {
        "customer_id": customer_id,
        "axes": axes,
        "schedule": schedule,
        "unsubscribe_token": token,
        "active": True,
        "created_at": date.today().isoformat(),
    }
    if days:
        record["delivery_days"] = days

    subscribers.append(record)
    _save(subscribers)

    return (
        f"등록 완료: customer_id={customer_id}\n\n"
        f"다음 단계(수동, 이 스크립트가 대신 못 함):\n"
        f"1. GitHub repo Settings → Secrets → CPO_SUBSCRIBER_EMAILS 값에 아래 키를 병합:\n"
        f'   "{customer_id}": "실제이메일주소"\n'
        f"2. 이 diff(data/subscribers/subscribers.json)를 커밋·push\n"
        f"3. (선택) workflow_dispatch로 crawl-and-build를 CPO_FORCE_SEND=true로 한 번 실행해 테스트 발송"
    )


def cli():
    parser = argparse.ArgumentParser(description="신규 구독자 등록")
    parser.add_argument("--customer-id", help="고유 식별자 (이메일 아님, PII 없는 슬러그)")
    parser.add_argument("--axes", help="콤마로 구분된 축 목록")
    parser.add_argument("--schedule", default="weekday", help="기본값 weekday (일간 구독)")
    parser.add_argument("--days", help="콤마로 구분된 수신 요일 (선택, 예: mon,wed,fri)")
    parser.add_argument("--list", action="store_true", help="현재 구독자 목록 출력 (PII 없음)")
    args = parser.parse_args()

    if args.list:
        for sub in _load():
            print(f"[{sub['customer_id']}] axes={sub.get('axes')} schedule={sub.get('schedule')} "
                  f"days={sub.get('delivery_days') or '기본값(평일 전체)'} active={sub.get('active', True)}")
        return

    if not args.customer_id or not args.axes:
        parser.error("--customer-id와 --axes 둘 다 필요합니다 (또는 --list)")

    axes = [a.strip() for a in args.axes.split(",") if a.strip()]
    days = [d.strip().lower() for d in args.days.split(",") if d.strip()] if args.days else None
    print(add_subscriber(args.customer_id, axes, args.schedule, days))


if __name__ == "__main__":
    sys.exit(cli())
