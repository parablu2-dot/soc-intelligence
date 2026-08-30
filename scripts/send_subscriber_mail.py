"""
send_subscriber_mail.py — 구독자별 맞춤 다축 메일링 (2026-08-11 구독시스템, 2026-08-16 다축 확장).

원래 스펙은 CPO(광통신) 단일 축이었으나, 실제 고객 요청은 "AI 서버(hpc_datacenter) +
패키지 신기술(packaging) + CPO/광통신(cpo_optics)" 3개 분야 묶음 메일. subscribers.json의
axis(단수) 필드를 axes(복수, 리스트)로 바꿔 구독자별 임의 축 조합을 지원한다(향후 다른 고객이
다른 조합을 원해도 프레임 변경 없이 커버 — YAGNI 원칙 유지, 파일명만 send_cpo_subscriber_mail.py
→ send_subscriber_mail.py로 개명해 실제 범위를 반영).

콘텐츠 소스 (재계산·재요약 없음, runtime-token-zero 유지):
  - cpo_optics 축: data/refined/cpo_optics/digest.json (scripts/summarize_cpo_axis.py 산출물,
    공개 5축 파이프라인과 분리된 전용 다이제스트)
  - 나머지 축(hpc_datacenter/packaging 등 5축 소속): data/refined/sector_summaries.json —
    이미 매일 전체 방문자용으로 생성되는 공개 산출물을 그대로 재사용(중복 LLM 호출 없음).
    관련 기사 링크는 data/refined/{axis}/*.json을 직접 읽어 최신순 상위 N개 선정.

스케줄: 이 고객 전용 "평일 1회". 크론 자체(crawl-and-build.yml)는 매일 20:00 UTC(KST 05:00 익일)
실행되므로, 이 스크립트가 KST 기준 평일 여부를 직접 판단해 주말엔 조용히 스킵한다(신규 cron 불필요).

구독자 정보:
  - data/subscribers/subscribers.json (git 커밋, PII 없음) — customer_id/axes/schedule/
    unsubscribe_token/active만 담음. public repo라 이메일은 여기 안 둠.
  - CPO_SUBSCRIBER_EMAILS 환경변수 (GitHub secret, JSON: {"customer_id": "email"}) — 실제 이메일은
    이쪽에만 존재. 이름은 CPO로 남아있지만(기존 secret 재사용, 사용자가 이미 등록해 둠) 실제로는
    이 구독 시스템 전체의 이메일 매핑을 담당. 기존 REVIEW_MAIL_TO 시크릿과 동일한 격리 패턴.

Unsubscribe: mailto:(SMTP_USER, subject에 토큰) 링크만 제공 — 자동 처리 백엔드 없음(Open Item 2
결정, process_unsubscribe.py 참고). 발송 실패해도 워크플로 전체가 죽지 않도록 항상 exit 0.
"""
from __future__ import annotations

import json
import os
import smtplib
import sys
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.subscriber_schema import AXES_ACTIVE  # noqa: E402 — sys.path 조정 후 import 필요

DATA_REFINED = ROOT / "data" / "refined"
SUBSCRIBERS_PATH = ROOT / "data" / "subscribers" / "subscribers.json"
STATUS_PATH = ROOT / "data" / "refined" / "subscriber_mail_status.json"

_MAX_LINKS_PER_AXIS = 5

# 고객이 실제 쓴 표현 그대로 — 대시보드의 일반 축 라벨(axisLabel(), "HPC·DC"/"Packaging")과는
# 별개로, 이 메일은 이 고객의 요청 문구("AI 서버"/"패키지 신기술"/"CPO 같은 광통신 기술")를 따른다.
_MAIL_AXIS_LABELS = {
    "mobile_ap": "Mobile AP",
    "hpc_datacenter": "AI 서버",
    "custom_soc": "Custom SoC",
    "foundry": "Foundry",
    "packaging": "패키지 신기술",
    "cpo_optics": "CPO/광통신",
}


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


def _axis_links(axis: str, limit: int = _MAX_LINKS_PER_AXIS) -> list[dict]:
    """data/refined/{axis}/*.json(모든 company 파일)을 합쳐 최신순 상위 N개 링크를 뽑는다."""
    axis_dir = DATA_REFINED / axis
    if not axis_dir.exists():
        return []
    items = []
    for f in axis_dir.glob("*.json"):
        data = _load_json(f)
        if isinstance(data, list):
            items.extend(data)
    items.sort(key=lambda it: it.get("published_date") or "", reverse=True)
    return [
        {k: it.get(k, "") for k in ("headline", "url", "source", "published_date")}
        for it in items[:limit]
    ]


def _gather_axis_content(axis: str) -> tuple[dict, list[dict], int]:
    """축 하나의 (content{ko,en}, links, item_count)를 반환.

    2026-08-30 일반화: cpo_optics 하나만 하드코딩하던 분기를 "축 폴더에 digest.json이 있으면
    그걸 쓴다"는 규칙으로 바꿈 — hbm/pmic처럼 5축 공개 파이프라인과 분리된 축이 늘어나도
    (summarize_{axis}_axis.py 패턴, cpo_optics 선례) 이 함수를 다시 손댈 필요가 없다."""
    digest_path = DATA_REFINED / axis / "digest.json"
    if digest_path.exists():
        digest = _load_json(digest_path)
        return digest.get("content") or {}, digest.get("links") or [], digest.get("item_count", 0)

    sector_data = _load_json(DATA_REFINED / "sector_summaries.json")
    info = (sector_data.get("sectors") or {}).get(axis) or {}
    return info.get("content") or {}, _axis_links(axis), info.get("item_count", 0)


def _axis_display_order(sub: dict, axes: list[str]) -> list[str]:
    """표시 순서 조정 훅 (Phase 4, 2026-08-30 기획 §7.2).

    관심도 반영은 "표시 순서만" — 축을 목록에서 제거하지 않는다(시계열 유지 원칙). 지금은
    구독자별 관심도 데이터가 전혀 없으므로 항등 함수로 둔다(기본값=구독 시점 등록 순서 그대로).
    나중에 관심도 데이터(열람 로그 등)가 쌓이면 이 함수 내부 정렬 로직만 채우면 되고,
    호출부(run())는 변경할 필요가 없다."""
    return list(axes)


def _axis_block_html(label: str, content: dict, links: list[dict]) -> str:
    ko = content.get("ko") or {}
    en = content.get("en") or {}
    if not ko and not en and not links:
        return ""

    def summary_block(c: dict) -> str:
        if not c:
            return ""
        facts = "".join(f'<li style="margin-bottom:2px">{f}</li>' for f in c.get("key_facts") or [])
        implications = "".join(
            f'<div style="margin-bottom:2px"><strong>[{im["keyword"]}]</strong> {im["text"]}</div>'
            for im in c.get("implications") or []
        )
        counterpoint = c.get("counterpoint") or ""
        return f"""\
<div style="font-size:13px;line-height:1.6;color:#e6edf3">{c.get("executive_summary", "")}</div>
{f'<ul style="margin:6px 0 0 16px;padding:0;font-size:12px;line-height:1.6;color:#e6edf3">{facts}</ul>' if facts else ''}
{f'<div style="margin-top:6px;font-size:12px;line-height:1.6;color:#e6edf3">{implications}</div>' if implications else ''}
{f'<div style="margin-top:6px;font-size:12px;color:#8b949e">▸ {counterpoint}</div>' if counterpoint else ''}"""

    links_html = ""
    if links:
        rows = "".join(
            f'<li style="margin-bottom:4px">'
            f'<a href="{lk["url"]}" style="color:#e6edf3;text-decoration:none;font-weight:600">{lk["headline"]}</a><br>'
            f'<span style="color:#8b949e;font-size:11px">{lk.get("source", "")} · {lk.get("published_date", "")}</span>'
            f'</li>'
            for lk in links
        )
        links_html = f'<ul style="margin:6px 0 0 16px;padding:0;list-style:disc;font-size:12px">{rows}</ul>'

    return f"""\
<div style="margin-bottom:20px">
  <div style="font-size:13px;font-weight:700;color:#58a6ff;margin-bottom:6px">◆ {label}</div>
  <div style="font-size:11px;font-weight:600;color:#8b949e;margin-bottom:2px">한국어</div>
  {summary_block(ko)}
  {f'<div style="font-size:11px;font-weight:600;color:#8b949e;margin:8px 0 2px">English</div>{summary_block(en)}' if en else ''}
  {f'<div style="font-size:11px;font-weight:600;color:#8b949e;margin-top:8px">관련 기사</div>{links_html}' if links_html else ''}
</div>"""


def _axis_change_mailto(smtp_user: str, unsubscribe_token: str, current_axes: list[str]) -> str:
    """구독 축 변경 요청용 mailto 링크 (2026-08-30, process_unsubscribe.py의 mailto+토큰 패턴 재사용).

    unsubscribe_token을 그대로 재사용한다 — 별도 change_token을 신설하지 않음(토큰 종류가
    늘어나면 subscribers.json 스키마·메일 템플릿이 같이 늘어나는데, 지금은 토큰 하나로 해지/
    변경 둘 다 식별 가능하면 충분). 실제 반영은 process_axis_change.py(수동 workflow_dispatch)가
    담당 — 자동 처리 백엔드 없음(unsubscribe와 동일 YAGNI 판단, 1~2고객 규모)."""
    subject = f"SoC Intelligence 축 변경 요청: {unsubscribe_token}"
    body = (
        f"현재 구독 축: {', '.join(current_axes)}\n\n"
        f"선택 가능한 축: {', '.join(AXES_ACTIVE)}\n\n"
        "원하시는 축 조합을 콤마로 구분해 이 메일에 답장해주세요."
    )
    # urlencode()는 공백을 '+'로 인코딩하는데 mailto: body에서는 메일 클라이언트마다 '+'를
    # 리터럴로 남기는 경우가 있어(RFC 6068은 percent-encoding을 요구) quote()로 직접 인코딩.
    query = f"subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
    return f"mailto:{smtp_user}?{query}"


def _build_html(axes: list[str], date_str: str, smtp_user: str, unsubscribe_token: str) -> tuple[str, bool]:
    """(html, has_content) 반환 — has_content=False면 보낼 내용이 없다는 뜻."""
    blocks = []
    has_content = False
    for axis in axes:
        content, links, item_count = _gather_axis_content(axis)
        block = _axis_block_html(_MAIL_AXIS_LABELS.get(axis, axis), content, links)
        if block:
            has_content = True
            blocks.append(block)

    unsubscribe_mailto = f"mailto:{smtp_user}?subject=SoC Intelligence 구독 해지 요청: {unsubscribe_token}"
    axis_change_mailto = _axis_change_mailto(smtp_user, unsubscribe_token, axes)

    html = f"""\
<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:20px;max-width:640px;margin:0 auto">
  <h2 style="color:#e6edf3;font-size:16px;margin-bottom:4px">SoC Intelligence — 맞춤 브리핑</h2>
  <div style="color:#8b949e;font-size:12px;margin-bottom:16px">{date_str}</div>
  {"".join(blocks)}
  <div style="margin-top:20px;padding-top:12px;border-top:1px solid #30363d;font-size:11px;color:#8b949e">
    <a href="{axis_change_mailto}" style="color:#8b949e">구독 축 변경</a>
    &nbsp;·&nbsp;
    <a href="{unsubscribe_mailto}" style="color:#8b949e">구독 해지</a>
  </div>
</div>"""
    return html, has_content


def _write_status(status: str, detail: str, sent: int = 0, skipped: int = 0,
                   per_subscriber: list[dict] | None = None) -> None:
    """실행 결과를 data/refined/에 커밋 대상 파일로 남긴다 (2026-08-30 추가).

    이유: 이 스크립트는 워크플로 전체를 안 죽이려고 항상 exit 0으로 끝나고, GitHub Actions
    step도 continue-on-error라 "success"로 찍힌다 — 즉 조용히 스킵돼도 Actions 탭에서는
    구분이 안 된다(실제로 첫 고객이 2주째 메일을 못 받은 원인 파악이 로그 접근 권한 없이는
    불가능했던 문제). 이 파일이 매일 커밋되므로 git으로 원인을 바로 확인할 수 있다."""
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps({
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": status,          # "sent" | "no_secrets" | "weekend_skip" | "bad_email_json" |
                                    # "no_active_subscribers" | "smtp_connect_failed"
        "detail": detail,
        "sent": sent,
        "skipped": skipped,
        "per_subscriber": per_subscriber or [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def run() -> None:
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    emails_raw = os.environ.get("CPO_SUBSCRIBER_EMAILS")

    if not (smtp_user and smtp_pass and emails_raw):
        print("::warning::SMTP_USER/SMTP_PASS/CPO_SUBSCRIBER_EMAILS 미설정 — 구독자 메일 발송 스킵")
        _write_status("no_secrets", "SMTP_USER/SMTP_PASS/CPO_SUBSCRIBER_EMAILS 중 하나 이상 미설정")
        return

    if not _is_kst_weekday() and not _force_send():
        print("[send_subscriber_mail] KST 주말 — 평일 1회 스케줄이라 스킵 "
              "(CPO_FORCE_SEND=true로 테스트 발송 가능)")
        _write_status("weekend_skip", "KST 기준 주말이라 평일 1회 스케줄 스킵")
        return

    try:
        email_map: dict = json.loads(emails_raw)
    except Exception as exc:
        print(f"::warning::CPO_SUBSCRIBER_EMAILS JSON 파싱 실패: {exc}")
        _write_status("bad_email_json", f"CPO_SUBSCRIBER_EMAILS JSON 파싱 실패: {exc}")
        return

    subscribers_raw = json.loads(SUBSCRIBERS_PATH.read_text(encoding="utf-8")) if SUBSCRIBERS_PATH.exists() else []
    subscribers = subscribers_raw if isinstance(subscribers_raw, list) else []
    subscribers = [
        s for s in subscribers
        if s.get("axes") and s.get("schedule") == "weekday" and s.get("active", True)
    ]
    if not subscribers:
        print("[send_subscriber_mail] 활성 구독자 없음 — 스킵")
        _write_status("no_active_subscribers", "axes/schedule=weekday/active 조건을 만족하는 구독자 없음")
        return

    date_str = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat() if ZoneInfo else ""
    sent, skipped = 0, 0
    per_subscriber: list[dict] = []

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
                    per_subscriber.append({"customer_id": customer_id, "result": "no_email_mapped",
                                            "note": "CPO_SUBSCRIBER_EMAILS에 이 customer_id 키가 없음"})
                    continue
                try:
                    ordered_axes = _axis_display_order(sub, sub["axes"])
                    html, has_content = _build_html(
                        ordered_axes, date_str, smtp_user, sub.get("unsubscribe_token", ""),
                    )
                    if not has_content:
                        print(f"[send_subscriber_mail] customer_id={customer_id}: "
                              f"구독 축 전부 최근 수집분 없음 — 스킵")
                        skipped += 1
                        per_subscriber.append({"customer_id": customer_id, "result": "no_content",
                                                "note": "구독 축 전부 오늘자 콘텐츠 없음"})
                        continue
                    msg = MIMEMultipart("alternative")
                    msg["Subject"] = f"SoC Intelligence — 맞춤 브리핑 — {date_str}"
                    msg["From"] = smtp_user
                    msg["To"] = mail_to
                    msg.attach(MIMEText(html, "html", "utf-8"))
                    server.sendmail(smtp_user, [mail_to], msg.as_string())
                    sent += 1
                    per_subscriber.append({"customer_id": customer_id, "result": "sent"})
                    print(f"[send_subscriber_mail] sent to customer_id={customer_id} axes={sub['axes']}")
                except Exception as exc:
                    print(f"::warning::customer_id={customer_id} 발송 실패: {exc}")
                    skipped += 1
                    per_subscriber.append({"customer_id": customer_id, "result": "send_failed", "note": str(exc)})
    except Exception as exc:
        print(f"::warning::send_subscriber_mail SMTP 연결 실패: {exc}")
        _write_status("smtp_connect_failed", str(exc))
        return

    print(f"[send_subscriber_mail] sent={sent} skipped={skipped}")
    _write_status("sent" if sent else "sent_zero", f"sent={sent} skipped={skipped}",
                  sent=sent, skipped=skipped, per_subscriber=per_subscriber)


if __name__ == "__main__":
    run()
    sys.exit(0)  # 메일 실패가 워크플로 job 전체를 죽이지 않도록 항상 0 (send_review_mail.py와 동일)
