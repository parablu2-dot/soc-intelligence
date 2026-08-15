#!/usr/bin/env python3
"""
process_unsubscribe.py — CPO 구독 해지 토큰 처리 (2026-08-11 구독시스템 스펙, Open Item 2).

설계 원칙 (narrative_trap_case.py와 동일한 git-as-storage 패턴 계승):
- 이메일 unsubscribe 링크는 mailto:(SMTP_USER, subject에 토큰 포함)로만 구성 — 자동 처리 서버리스
  백엔드(Cloudflare Pages Function 등)는 만들지 않는다(1고객 규모에서 과설계, 스펙의 "멀티고객
  자동화 로직 지금 안 만듦" 제약과 정합).
- 운영자가 메일로 받은 토큰을 이 CLI(또는 동명 workflow_dispatch)에 입력하면 실제로 검증 후
  data/subscribers/subscribers.json의 해당 항목을 active=false로 갱신·커밋한다.
- subscribers.json은 PII(이메일) 없이 customer_id/axes/schedule/unsubscribe_token/active만 담는다
  (repo가 public이라 이메일은 GitHub secret CPO_SUBSCRIBER_EMAILS에만 존재 — subscribers.json과
  분리 보관).

사용법:
    python scripts/process_unsubscribe.py --token <token>
    python scripts/process_unsubscribe.py --list
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBSCRIBERS_PATH = ROOT / "data" / "subscribers" / "subscribers.json"


def _load() -> list[dict]:
    if not SUBSCRIBERS_PATH.exists():
        return []
    return json.loads(SUBSCRIBERS_PATH.read_text(encoding="utf-8"))


def _save(subscribers: list[dict]) -> None:
    SUBSCRIBERS_PATH.write_text(
        json.dumps(subscribers, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )


def process_token(token: str) -> str:
    """토큰을 검증하고 매칭 구독자를 비활성화한다. 결과 메시지를 반환한다."""
    subscribers = _load()
    for sub in subscribers:
        if sub.get("unsubscribe_token") == token:
            if not sub.get("active", True):
                return f"이미 비활성 상태입니다: customer_id={sub['customer_id']}"
            sub["active"] = False
            sub["unsubscribed_at"] = datetime.now(timezone.utc).isoformat()
            _save(subscribers)
            axes = ",".join(sub.get("axes") or [sub.get("axis", "")])  # axes(신규)/axis(구버전) 모두 대응
            return f"구독 해지 완료: customer_id={sub['customer_id']} axes={axes}"
    return "일치하는 토큰을 찾지 못했습니다 (이미 처리됐거나 잘못된 토큰일 수 있음)"


def cli():
    parser = argparse.ArgumentParser(description="CPO 구독 해지 토큰 처리")
    parser.add_argument("--token", help="구독 해지할 unsubscribe_token")
    parser.add_argument("--list", action="store_true", help="현재 구독자 목록 출력 (PII 없음)")
    args = parser.parse_args()

    if args.list:
        for sub in _load():
            axes = ",".join(sub.get("axes") or [sub.get("axis", "")])  # axes(신규)/axis(구버전) 모두 대응
            print(f"[{sub['customer_id']}] axes={axes} schedule={sub['schedule']} "
                  f"active={sub.get('active', True)}")
        return

    if not args.token:
        parser.error("--token 또는 --list 중 하나는 필요합니다")

    print(process_token(args.token))


if __name__ == "__main__":
    sys.exit(cli())
