"""
summarize_cpo_axis.py — CPO(광통신) 9번째 축 전용 다이제스트 생성 (2026-08-11 구독시스템 스펙).

summarize_sectors.py(5축 공개 파이프라인)와 완전히 분리된 스크립트다. 의도적으로:
  - _AXES를 건드리지 않는다 (summarize_sectors.py는 여전히 5축만 처리)
  - 출력을 sector_summaries.json/daily_top5.json에 섞지 않는다
    (site/js/app.js·company_strategy.py 등 공개 소비처가 이 파일을 안 읽으므로 안전)
이유: 스펙 요구사항 — CPO는 "9번째 독립 축", 초기 전용 서비스 단계라 기존 5축 대시보드에 노출 금지.

스케줄: 이 고객은 "평일 1회" 수신. 크론 자체는 매일(주말 포함) 20:00 UTC(KST 05:00 익일) 실행되므로,
KST 월요일에 실행될 때는 주말 수집분(금~일)이 누락되지 않도록 3일치를 함께 훑는다. 그 외 요일은
당일(전날 저녁 기준 KST 당일)분만 본다. 발송 여부(평일 게이팅)는 send_cpo_subscriber_mail.py가
별도로 판단한다 — 이 스크립트는 요일과 무관하게 매일 실행해 데이터를 최신 상태로 유지한다.

출력: data/refined/cpo_optics/digest.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover — Python 3.9+ 표준 라이브러리, 방어적 처리만
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db
from scripts.summary_schema import content_tool_schema, translate_content_batch

_AXIS = "cpo_optics"
_AXIS_LABEL = "CPO/광통신"
_MAX_ITEMS = 15          # 배치 호출 입력 상한 (비용 가드, summarize_sectors.py와 동일 기준)
_MAX_LINKS = 5            # 메일에 넣을 관련 기사 링크 상한

DIGEST_PATH = ROOT / "data" / "refined" / "cpo_optics" / "digest.json"

_PROMPT_TMPL = """\
You are a semiconductor/photonics competitive intelligence analyst writing a short digest for a \
single customer subscribed to the CPO(Co-Packaged Optics)/optical communications sector only.

Below are recently collected headlines for this sector. Produce a structured Korean summary via \
the tool call: executive_summary (2-3 sentences), key_facts (one line per concrete number/proper \
noun), implications (keyword+text pairs), counterpoint (one line caveat, empty string if none).

Rules (hard constraints):
- Base the summary ONLY on the headlines/summaries given below — do not invent facts.
- Do not include filler like "Today's headlines show".
- Be specific: technology, companies, product/spec moves (transceiver speed, node, partnership).
- If there isn't enough material for a field, use an empty array/string — do not fabricate.
- No emoji.

### {axis} ({count} items)
{lines}
"""


def _kst_today() -> date:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Seoul")).date()
    return datetime.now(timezone.utc).date()  # 방어적 폴백 — 실제로는 항상 zoneinfo 사용


def _lookback_days(today_kst: date) -> int:
    """평일 1회 발송 스케줄이라 KST 월요일엔 주말(금~일) 수집분을 놓치지 않게 lookback을 넓힌다."""
    return 3 if today_kst.weekday() == 0 else 1  # 0=Monday


def _fetch_recent_items(conn, since: date) -> list[dict]:
    rows = conn.execute("""
        SELECT DISTINCT
            cn.id, cn.axis, cn.company, cn.title, cn.verification, cn.inference
        FROM raw_documents rd
        JOIN merge_log ml ON ml.raw_id = rd.id
        JOIN canonical_nodes cn ON ml.canonical_id = cn.id
        WHERE cn.axis = ?
          AND date(rd.crawled_at) >= date(?)
          AND ml.decision != 'noise'
    """, (_AXIS, since.isoformat())).fetchall()

    items = []
    for row in rows:
        v = json.loads(row["verification"])
        inf = json.loads(row["inference"])
        items.append({
            "company": row["company"],
            "headline": row["title"],
            "summary": inf.get("summary") or "",
            "tags": inf.get("tags") or [],
            "url": v.get("url") or "",
            "source": v.get("source") or "",
            "published_date": v.get("published_date") or "",
        })
    return items


def _generate_digest_content(items: list[dict], client) -> dict:
    lines = "\n".join(
        f"- {it['headline']}" + (f" — {it['summary']}" if it["summary"] else "")
        for it in items[:_MAX_ITEMS]
    )
    prompt = _PROMPT_TMPL.format(axis=_AXIS, count=len(items), lines=lines)
    tool_schema = content_tool_schema(
        "cpo_digest",
        "Structured competitive-intelligence summary for the CPO/optical-comms sector, in Korean",
        [_AXIS],
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,  # summarize_sectors.py와 동일 값 — 1024는 tool-call JSON이 잘릴 위험
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": "cpo_digest"},
    )
    tool_block = next(b for b in resp.content if b.type == "tool_use")
    ko_content: dict = tool_block.input

    en_content = translate_content_batch(
        client, ko_content, "cpo_digest_en", "English translation mirror of the CPO digest",
    )
    return {"ko": ko_content.get(_AXIS, {}), "en": en_content.get(_AXIS, {})}


def _recency_sort_key(item: dict) -> str:
    return item["published_date"] or ""


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    today_kst = _kst_today()
    since = today_kst - timedelta(days=_lookback_days(today_kst) - 1)

    init_db()
    conn = get_conn()
    try:
        items = _fetch_recent_items(conn, since)
    finally:
        conn.close()

    print(f"[summarize_cpo_axis] {since.isoformat()}~{today_kst.isoformat()} 수집분 {len(items)}건")

    content = {"ko": {}, "en": {}}
    if items and api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            content = _generate_digest_content(items, client)
        except Exception as exc:
            print(f"::warning::summarize_cpo_axis digest generation failed: {type(exc).__name__}: {exc}")
    elif items:
        print("::warning::ANTHROPIC_API_KEY not set — CPO digest summary skipped (links만 생성)")

    links = sorted(items, key=_recency_sort_key, reverse=True)[:_MAX_LINKS]
    links = [{k: it[k] for k in ("headline", "url", "source", "published_date")} for it in links]

    now_ts = datetime.now(timezone.utc).isoformat()
    DIGEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    DIGEST_PATH.write_text(
        json.dumps({
            "axis": _AXIS,
            "sector": _AXIS_LABEL,
            "date": today_kst.isoformat(),
            "generated_at": now_ts,
            "item_count": len(items),
            "content": content,
            "links": links,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[summarize_cpo_axis] items={len(items)} links={len(links)} → {DIGEST_PATH.name}")


if __name__ == "__main__":
    sys.exit(run())
