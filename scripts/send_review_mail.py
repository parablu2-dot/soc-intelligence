"""
send_review_mail.py — 일일 리뷰 메일링 (Phase 6, self-test).

Phase 3에서 이미 정적 저장된 data/refined/daily_top5.json, sector_summaries.json을
그대로 이메일 본문으로 렌더한다. 재계산·재요약 없음 (runtime-token-zero 유지).
수신자는 천 1인 — 구독자 시스템 없음(YAGNI). 발송 실패해도 워크플로 전체가 죽지 않도록
이 스크립트 자체도 예외를 삼키고 항상 exit 0 (워크플로 쪽 continue-on-error와 이중 격리).
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_REFINED = ROOT / "data" / "refined"

SITE_URL = "https://soc-intelligence.pages.dev/#review"

_AXIS_LABELS = {
    "mobile_ap": "Mobile AP",
    "hpc_datacenter": "HPC·DC",
    "custom_soc": "Custom SoC",
    "foundry": "Foundry",
    "packaging": "Packaging",
}


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_html(top5: list[dict], sectors: dict, date: str) -> str:
    top5_rows = "".join(
        f'<tr><td style="padding:6px 0;vertical-align:top;font-weight:600;color:#58a6ff">{i+1}.</td>'
        f'<td style="padding:6px 0 6px 8px">'
        f'<a href="{t["url"]}" style="color:#e6edf3;text-decoration:none;font-weight:600">{t["headline"]}</a><br>'
        f'<span style="color:#8b949e;font-size:12px">[{_AXIS_LABELS.get(t["axis"], t["axis"])}] {t["source"]} · {t["published_date"]}</span>'
        f'</td></tr>'
        for i, t in enumerate(top5)
    )

    sector_blocks = "".join(
        f'<div style="margin-bottom:14px">'
        f'<div style="font-weight:600;color:#58a6ff;font-size:13px;margin-bottom:4px">{_AXIS_LABELS.get(axis, axis)}</div>'
        f'<div style="font-size:13px;line-height:1.6;color:#e6edf3">{info.get("summary", "")}</div>'
        f'</div>'
        for axis, info in sectors.items() if info.get("summary")
    )

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:20px;max-width:640px;margin:0 auto">
  <h2 style="color:#e6edf3;font-size:16px;margin-bottom:4px">SoC Intelligence — 일일 리뷰</h2>
  <div style="color:#8b949e;font-size:12px;margin-bottom:16px">{date}</div>

  <div style="font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:8px">★ 일일 Summary — Top 5</div>
  <table style="width:100%;border-collapse:collapse;margin-bottom:20px">{top5_rows}</table>

  <div style="font-size:12px;font-weight:600;color:#58a6ff;margin-bottom:8px">◉ 섹터별 요약</div>
  {sector_blocks}

  <div style="margin-top:20px;padding-top:12px;border-top:1px solid #30363d;font-size:12px">
    <a href="{SITE_URL}" style="color:#58a6ff">{SITE_URL}</a>
  </div>
</div>"""


def run() -> None:
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    mail_to = os.environ.get("REVIEW_MAIL_TO")

    if not (smtp_user and smtp_pass and mail_to):
        print("::warning::SMTP_USER/SMTP_PASS/REVIEW_MAIL_TO 미설정 — 메일 발송 스킵")
        return

    top5_data = _load_json(DATA_REFINED / "daily_top5.json")
    sector_data = _load_json(DATA_REFINED / "sector_summaries.json")
    top5 = top5_data.get("top5", [])
    sectors = sector_data.get("sectors", {})
    date = top5_data.get("date") or sector_data.get("date") or ""

    if not top5 and not sectors:
        print("[send_review_mail] Phase 3 산출물 없음 — 발송 스킵")
        return

    html = _build_html(top5, sectors, date)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"SoC Intelligence 일일 리뷰 — {date}"
    msg["From"] = smtp_user
    msg["To"] = mail_to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, [mail_to], msg.as_string())
        print(f"[send_review_mail] sent to {mail_to} (top5={len(top5)}, sectors={len(sectors)})")
    except Exception as exc:
        print(f"::warning::send_review_mail failed: {exc}")


if __name__ == "__main__":
    run()
    sys.exit(0)  # 메일 실패가 워크플로 job 전체를 죽이지 않도록 항상 0 (워크플로 continue-on-error와 이중 격리)
