"""
send_cpo_subscriber_mail.py — CPO(광통신) 축 구독자 메일링 (2026-08-11 구독시스템 스펙).

data/refined/cpo_optics/digest.json(scripts/summarize_cpo_axis.py 산출물)을 그대로 렌더한다.
재계산·재요약 없음 (runtime-token-zero 유지, send_review_mail.py와 동일 원칙).

스케줄: 이 고객 전용 "평일 1회". 크론 자체(crawl-and-build.yml)는 매일 20:00 UTC(KST 05:00 익일)
실행되므로, 이 스크립트가 KST 기준 평일 여부를 직접 판단해 주말엔 조용히 스킵한다(신규 cron 불필요).

구독자 정보:
  - data/subscribers/subscribers.json (git 커밋, PII 없음) — customer_id/axis/schedule/
    unsubscribe_token/active만 담음. public repo라 이메일은 여기 안 둠.
  - CPO_SUBSCRIBER_EMAILS 환경변수 (GitHub secret, JSON: {"customer_id": "email"}) — 실제 이메일은
    이쪽에만 존재. 기존 REVIEW_MAIL_TO 시크릿과 동일한 격리 패턴.

Unsubscribe: mailto:(SMTP_USER, subject에 토큰) 링크만 제공 — 자동 처리 백엔드 없음(Open Item 2
결정, process_unsubscribe.py 참고). 발송 실패해도 워크플로 전체가 죽지 않도록 항상 exit 0.
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
DATA_REFINED = ROOT / "data" / "refined"
SUBSCRIBERS_PATH = ROOT / "data" / "subscribers" / "subscribers.json"

_AXIS = "cpo_optics"
_AXIS_LABEL = "CPO/광통신"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _is_kst_weekday() -> bool:
    if ZoneInfo is not None:
        now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
    else:  # pragma: no cover — 방어적 폴백
        now_kst = datetime.utcnow()
    return now_kst.weekday() < 5  # 0=Mon ... 4=Fri


def _force_send() -> bool:
    """workflow_dispatch 수동 테스트용 — 주말에도 발송 검증할 수 있게 게이트 우회.
    cron(스케줄 실행)에는 이 env가 안 실리므로 평소 평일 게이팅은 그대로 유지됨."""
    return os.environ.get("CPO_FORCE_SEND", "").lower() in ("1", "true", "yes")


def _links_html(links: list[dict]) -> str:
    if not links:
        return ""
    rows = "".join(
        f'<li style="margin-bottom:6px">'
        f'<a href="{lk["url"]}" style="color:#e6edf3;text-decoration:none;font-weight:600">{lk["headline"]}</a><br>'
        f'<span style="color:#8b949e;font-size:12px">{lk.get("source", "")} · {lk.get("published_date", "")}</span>'
        f'</li>'
        for lk in links
    )
    return f'<ul style="margin:8px 0 0 16px;padding:0;list-style:disc;font-size:13px">{rows}</ul>'


def _sector_block_html(content: dict, lang: str) -> str:
    c = content.get(lang) or {}
    if not c:
        return ""
    facts = "".join(f'<li style="margin-bottom:2px">{f}</li>' for f in c.get("key_facts") or [])
    implications = "".join(
        f'<div style="margin-bottom:2px"><strong>[{im["keyword"]}]</strong> {im["text"]}</div>'
        for im in c.get("implications") or []
    )
    counterpoint = c.get("counterpoint") or ""
    return f"""\
<div style="margin-bottom:16px">
  <div style="font-size:13px;line-height:1.6;color:#e6edf3">{c.get("executive_summary", "")}</div>
  {f'<ul style="margin:6px 0 0 16px;padding:0;font-size:12px;line-height:1.6;color:#e6edf3">{facts}</ul>' if facts else ''}
  {f'<div style="margin-top:6px;font-size:12px;line-height:1.6;color:#e6edf3">{implications}</div>' if implications else ''}
  {f'<div style="margin-top:6px;font-size:12px;color:#8b949e">▸ {counterpoint}</div>' if counterpoint else ''}
</div>"""


def _build_html(digest: dict, smtp_user: str, unsubscribe_token: str) -> str:
    date_str = digest.get("date", "")
    content = digest.get("content") or {}
    links = digest.get("links") or []
    unsubscribe_mailto = (
        f"mailto:{smtp_user}?subject={_AXIS_LABEL} 구독 해지 요청: {unsubscribe_token}"
    )

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:20px;max-width:640px;margin:0 auto">
  <h2 style="color:#e6edf3;font-size:16px;margin-bottom:4px">SoC Intelligence — {_AXIS_LABEL} 브리핑</h2>
  <div style="color:#8b949e;font-size:12px;margin-bottom:16px">{date_str}</div>

  <div style="font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:8px">◉ 요약 (한국어)</div>
  {_sector_block_html(content, "ko")}

  <div style="margin:16px 0;border-top:1px solid #30363d"></div>

  <div style="font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:8px">◉ Summary (English)</div>
  {_sector_block_html(content, "en")}

  <div style="margin:16px 0;border-top:1px solid #30363d"></div>

  <div style="font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:8px">▸ 관련 기사</div>
  {_links_html(links)}

  <div style="margin-top:20px;padding-top:12px;border-top:1px solid #30363d;font-size:11px;color:#8b949e">
    <a href="{unsubscribe_mailto}" style="color:#8b949e">구독 해지</a>
  </div>
</div>"""


def run() -> None:
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    emails_raw = os.environ.get("CPO_SUBSCRIBER_EMAILS")

    if not (smtp_user and smtp_pass and emails_raw):
        print("::warning::SMTP_USER/SMTP_PASS/CPO_SUBSCRIBER_EMAILS 미설정 — CPO 메일 발송 스킵")
        return

    if not _is_kst_weekday() and not _force_send():
        print("[send_cpo_subscriber_mail] KST 주말 — 평일 1회 스케줄이라 스킵 "
              "(CPO_FORCE_SEND=true로 테스트 발송 가능)")
        return

    try:
        email_map: dict = json.loads(emails_raw)
    except Exception as exc:
        print(f"::warning::CPO_SUBSCRIBER_EMAILS JSON 파싱 실패: {exc}")
        return

    subscribers_raw = json.loads(SUBSCRIBERS_PATH.read_text(encoding="utf-8")) if SUBSCRIBERS_PATH.exists() else []
    subscribers = subscribers_raw if isinstance(subscribers_raw, list) else []
    subscribers = [
        s for s in subscribers
        if s.get("axis") == _AXIS and s.get("schedule") == "weekday" and s.get("active", True)
    ]
    if not subscribers:
        print("[send_cpo_subscriber_mail] 활성 구독자 없음 — 스킵")
        return

    digest = _load_json(DATA_REFINED / "cpo_optics" / "digest.json")
    if not digest or not digest.get("item_count"):
        print("[send_cpo_subscriber_mail] 최근 수집분 없음 — 발송 스킵")
        return

    date_str = digest.get("date", "")
    sent, skipped = 0, 0

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)

            for sub in subscribers:
                customer_id = sub.get("customer_id", "")
                mail_to = email_map.get(customer_id)
                if not mail_to:
                    print(f"::warning::customer_id={customer_id}에 대한 이메일이 "
                          f"CPO_SUBSCRIBER_EMAILS에 없음 — 스킵")
                    skipped += 1
                    continue
                try:
                    html = _build_html(digest, smtp_user, sub.get("unsubscribe_token", ""))
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = f"SoC Intelligence — {_AXIS_LABEL} 브리핑 — {date_str}"
                    msg["From"] = smtp_user
                    msg["To"] = mail_to
                    msg.attach(MIMEText(html, "html", "utf-8"))
                    server.sendmail(smtp_user, [mail_to], msg.as_string())
                    sent += 1
                    print(f"[send_cpo_subscriber_mail] sent to customer_id={customer_id}")
                except Exception as exc:
                    print(f"::warning::customer_id={customer_id} 발송 실패: {exc}")
                    skipped += 1
    except Exception as exc:
        print(f"::warning::send_cpo_subscriber_mail SMTP 연결 실패: {exc}")
        return

    print(f"[send_cpo_subscriber_mail] sent={sent} skipped={skipped}")


if __name__ == "__main__":
    run()
    sys.exit(0)  # 메일 실패가 워크플로 job 전체를 죽이지 않도록 항상 0 (send_review_mail.py와 동일)
