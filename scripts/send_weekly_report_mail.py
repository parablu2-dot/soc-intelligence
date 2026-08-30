"""
send_weekly_report_mail.py — Weekly Report 페르소나별 발송 (Phase 3, 2026-08-30).

읽기만 함 — data/refined/weekly_report/latest.json(generate_weekly_report.py 산출물)을 그대로
페르소나별로 렌더(scripts/render_persona_reports.py)해 보낸다. LLM 재호출 없음(runtime-token-zero).

대상: subscribers.json에서 scripts/subscriber_schema.normalize_subscriber() 결과 schedule_kind
== "weekly"인 레코드. **2026-08-30 기준 이 조건을 만족하는 실 구독자가 없다** — persona/schedule
필드를 강제 부여하지 않기로 한 결정(Phase 1)의 결과로, 이 스크립트가 실수로 워크플로에서 돌아도
안전하게 0건 스킵된다(기존 send_subscriber_mail.py와 동일한 fail-soft 원칙 + 이번 스키마 설계가
만든 부수적 안전장치).

이메일 매핑은 기존 CPO_SUBSCRIBER_EMAILS secret을 그대로 재사용(send_subscriber_mail.py와 동일
격리 패턴 — customer_id 키로 이메일 조회, PII는 secret에만).
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.subscriber_schema import normalize_subscriber
from scripts.render_persona_reports import render_exec_html, render_leader_html, render_staff_html

SUBSCRIBERS_PATH = ROOT / "data" / "subscribers" / "subscribers.json"
LATEST_REPORT_PATH = ROOT / "data" / "refined" / "weekly_report" / "latest.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _kst_date_str() -> str:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    return datetime.now().date().isoformat()


def _force_send() -> bool:
    return os.environ.get("WEEKLY_FORCE_SEND", "").lower() in ("1", "true", "yes")


def _render_for(sub: dict, norm: dict, report: dict, date_str: str) -> str | None:
    persona = norm["persona"]
    domain_scope = norm["domain_scope"]
    if persona == "exec":
        return render_exec_html(report, date_str)
    if persona == "leader":
        return render_leader_html(report, domain_scope, date_str)
    if persona == "staff":
        axes_list = domain_scope["primary"] + domain_scope["adjacent"] or sub.get("axes") or []
        return render_staff_html(report, axes_list, date_str)
    # persona 미지정 레거시 구독자는 weekly 대상에서 제외(§9 "값 공란" 원칙 — persona 없이는
    # 어떤 포맷을 줘야 할지 판단 근거가 없음. 강제로 기본 포맷을 정하지 않는다).
    print(f"::warning::customer_id={sub.get('customer_id')} — persona 미지정, weekly 발송 스킵")
    return None


def run() -> None:
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    emails_raw = os.environ.get("CPO_SUBSCRIBER_EMAILS")

    if not (smtp_user and smtp_pass and emails_raw):
        print("::warning::SMTP_USER/SMTP_PASS/CPO_SUBSCRIBER_EMAILS 미설정 — weekly 발송 스킵")
        return

    report = _load_json(LATEST_REPORT_PATH)
    if not report:
        print("[send_weekly_report_mail] latest.json 없음 — generate_weekly_report.py 먼저 실행 필요")
        return

    try:
        email_map: dict = json.loads(emails_raw)
    except Exception as exc:
        print(f"::warning::CPO_SUBSCRIBER_EMAILS JSON 파싱 실패: {exc}")
        return

    subscribers_raw = _load_json(SUBSCRIBERS_PATH)
    subscribers = subscribers_raw if isinstance(subscribers_raw, list) else []

    eligible = []
    for sub in subscribers:
        if not sub.get("active", True):
            continue
        norm = normalize_subscriber(sub)
        if norm["schedule_kind"] != "weekly":
            continue
        eligible.append((sub, norm))

    if not eligible:
        print("[send_weekly_report_mail] schedule=weekly 구독자 없음 — 스킵"
              "(Phase 1 설계상 정상 — persona/schedule을 기존 레코드에 강제 부여하지 않았음)")
        return

    date_str = _kst_date_str()
    sent, skipped = 0, 0
    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)

            for sub, norm in eligible:
                customer_id = sub.get("customer_id", "")
                mail_to = email_map.get(customer_id)
                if not mail_to:
                    print(f"::warning::customer_id={customer_id} 이메일 없음 — 스킵")
                    skipped += 1
                    continue
                html = _render_for(sub, norm, report, date_str)
                if not html:
                    skipped += 1
                    continue
                try:
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = f"SoC Intelligence — Weekly Report ({norm['persona']}) — {date_str}"
                    msg["From"] = smtp_user
                    msg["To"] = mail_to
                    msg.attach(MIMEText(html, "html", "utf-8"))
                    server.sendmail(smtp_user, [mail_to], msg.as_string())
                    sent += 1
                    print(f"[send_weekly_report_mail] sent to customer_id={customer_id} persona={norm['persona']}")
                except Exception as exc:
                    print(f"::warning::customer_id={customer_id} 발송 실패: {exc}")
                    skipped += 1
    except Exception as exc:
        print(f"::warning::send_weekly_report_mail SMTP 연결 실패: {exc}")
        return

    print(f"[send_weekly_report_mail] sent={sent} skipped={skipped}")


if __name__ == "__main__":
    run()
    sys.exit(0)  # 메일 실패가 워크플로 전체를 죽이지 않도록 항상 0
