"""
summarize_pmic_axis.py — PMIC 10번째 축 전용 다이제스트 생성 (2026-08-30 페르소나 Verifier 기획 §8).

summarize_cpo_axis.py와 동일 구조(9번째 축 CPO 선례)지만 distillation 렌즈가 다르다(§8-2):
기존 SoC 기본 렌즈("접점에서 가치가 쌓인다" — 경쟁사 간 기술 접점에서 우위가 갈린다는 관점)를
쓰지 않는다. PMIC는 접점 경쟁축이 아니라 **BOM·공급 안정성 축** — 판단 기준이 성능 우위가
아니라 가격·캐파(가동률)·인증 등급(자동차/서버)이다. 성숙 공정(BCD) 축이라는 점도 프롬프트에
명시해 모델이 "선단 공정 경쟁" 프레임으로 오분석하지 않게 한다.

summarize_sectors.py(5축 공개 파이프라인)·site/js/app.js에는 의도적으로 배선하지 않는다
(CPO와 동일 원칙 — 별도 구독 전용 소비처, scripts/send_subscriber_mail.py가
`data/refined/pmic/digest.json` 존재 여부로 자동 인식함, Phase 4 일반화 참고).

출력: data/refined/pmic/digest.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db
from scripts.summary_schema import content_tool_schema, translate_content_batch

_AXIS = "pmic"
_AXIS_LABEL = "PMIC"
_MAX_ITEMS = 15
_MAX_LINKS = 5

DIGEST_PATH = ROOT / "data" / "refined" / "pmic" / "digest.json"

_PROMPT_TMPL = """\
You are a semiconductor supply-chain analyst writing a short digest for a single sector: PMIC \
(Power Management IC).

IMPORTANT — lens for this sector (do NOT use a leading-edge competitive-advantage framing here): \
PMIC is a mature-node (BCD process) sector. Judge it as a BOM / supply-stability axis, not a \
performance-competition axis. The relevant judgment criteria are price, fab capacity/utilization, \
and certification grade (automotive-grade, server-grade) — NOT process-node leadership or \
performance superiority.

Below are recently collected headlines for this sector. Produce a structured Korean summary via \
the tool call: executive_summary (2-3 sentences, BOM/supply-stability framing), key_facts (one \
line per concrete number/proper noun), implications (keyword+text pairs), counterpoint (one line \
caveat, empty string if none).

Rules (hard constraints):
- Base the summary ONLY on the headlines/summaries given below — do not invent facts.
- Do not include filler like "Today's headlines show".
- Be specific: capacity/utilization figures, pricing moves, certification/qualification news.
- If there isn't enough material for a field, use an empty array/string — do not fabricate.
- No emoji.

### {axis} ({count} items)
{lines}
"""


def _kst_today() -> date:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Seoul")).date()
    return datetime.now(timezone.utc).date()


def _lookback_days(today_kst: date) -> int:
    return 3 if today_kst.weekday() == 0 else 1  # 월요일엔 주말분 포함


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
        "pmic_digest",
        "Structured BOM/supply-stability summary for the PMIC sector, in Korean",
        [_AXIS],
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": "pmic_digest"},
    )
    tool_block = next(b for b in resp.content if b.type == "tool_use")
    ko_content: dict = tool_block.input

    en_content = translate_content_batch(
        client, ko_content, "pmic_digest_en", "English translation mirror of the PMIC digest",
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

    print(f"[summarize_pmic_axis] {since.isoformat()}~{today_kst.isoformat()} 수집분 {len(items)}건")

    content = {"ko": {}, "en": {}}
    if items and api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            content = _generate_digest_content(items, client)
        except Exception as exc:
            print(f"::warning::summarize_pmic_axis digest generation failed: {type(exc).__name__}: {exc}")
    elif items:
        print("::warning::ANTHROPIC_API_KEY not set — PMIC digest summary skipped (links만 생성)")

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
    print(f"[summarize_pmic_axis] items={len(items)} links={len(links)} → {DIGEST_PATH.name}")


if __name__ == "__main__":
    sys.exit(run())
