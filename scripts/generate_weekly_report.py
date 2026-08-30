"""
generate_weekly_report.py — Weekly Report 생성 (Phase 3, 2026-08-30 페르소나 Verifier 기획).

Phase 0 탐색에서 확인된 사실: soc-intelligence에는 "Weekly Report 파이프라인"이 이전에 존재하지
않았다(daily만 있었음). 이 스크립트가 그 파이프라인의 실체다 — 신규 구현.

빌드타임 LLM 호출 1회(축별 배치, summarize_sectors.py/summarize_cpo_axis.py와 동일 패턴) —
runtime-token-zero 원칙 유지(발송 시점엔 이 스크립트 산출물을 정적으로 읽기만 함).

입력 : DB(canonical_nodes) 최근 7일치, 축=AXES_ACTIVE(8축, DRAM/NAND 보류) 전부
       + eco-intelligence 매크로/태그 레이어(scripts/eco_client.py)
       + 지난주 산출물(data/refined/weekly_report/history.json) — "판단 변경" 비교용 컨텍스트
출력 : data/refined/weekly_report/{YYYY-MM-DD}.json (append-only 아카이브)
       data/refined/weekly_report/latest.json        (렌더러·발송 스크립트가 읽는 최신본)
       data/refined/weekly_report/history.json       (다음 주 비교용, 축별 executive_summary만 누적)

신호 없는 축(0건)은 LLM 호출 없이 "변화 없음" placeholder를 코드로 직접 채운다(비용 가드,
summarize_sectors.py의 "active만 호출" 관례와 동일) — 그래도 최종 출력에는 AXES_10 10개 전부가
자리를 채운 채로 들어간다(§4 "빈 축도 자리를 비우지 않는다").

HBM 축 소스에 대한 판단: 이번 구현 시점엔 HBM 전용 크롤러가 없다(mobile_ap/hpc_datacenter/
foundry/packaging 크롤러 안에 hbm/hbm3/hbm3e/hbm4 키워드 태그만 존재, crawlers/common/rss_utils.py
extract_tags 참고). "HBM=성능 병목 허브"라는 기획 §2의 구조적 발견과 맞춰, 신규 크롤러를 만드는
대신 **기존 축 전체에서 hbm 계열 태그가 붙은 신호를 모아 별도 축으로 집계**하는 방식을 택했다 —
PMIC처럼 전용 소스가 필요한 축이 아니라 이미 여러 축에 흩어져 있던 신호를 다시 묶는 축이기 때문.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.db.db import get_conn, init_db
from scripts.weekly_report_schema import weekly_tool_schema, translate_weekly_batch
from scripts.subscriber_schema import AXES_10, AXES_ACTIVE
from scripts import eco_client

WEEKLY_DIR = ROOT / "data" / "refined" / "weekly_report"
HISTORY_PATH = WEEKLY_DIR / "history.json"
LATEST_PATH = WEEKLY_DIR / "latest.json"
ECO_MAPPING_PATH = ROOT / "config" / "eco_soc_mapping.json"

_MAX_ITEMS_PER_AXIS = 20  # 주간이라 일간(15)보다 약간 여유
_MAX_ECO_LINES = 5
_HBM_TAGS = {"hbm", "hbm3", "hbm3e", "hbm4"}

_DEFAULT_ANCHOR = (
    "Default lens: value accrues at the technical interface (packaging, interposer, protocol "
    "boundary) between competing players. Judge competitive standing accordingly."
)
_PMIC_ANCHOR = (
    "PMIC lens (different from the default SoC lens — do NOT use a performance/competitive-edge "
    "framing here): this axis is a BOM / supply-stability axis, not a leading-edge competition "
    "axis. Judge by price, capacity (fab utilization), and certification grade (automotive/server) "
    "— NOT by performance superiority. This is a mature-node (BCD) axis."
)

_PROMPT_TMPL = """\
You are a semiconductor competitive intelligence analyst writing a WEEKLY digest (one paragraph \
of judgment per sector, not just a headline list).

{anchor}

Below is this week's collected material for sector "{axis}", plus (if any) related macro-economic \
notes tagged to this sector, plus last week's judgment for comparison.

Produce a structured Korean summary via the tool call:
  executive_summary        — 2-3 sentence JUDGMENT (not just a recap) for this week
  key_facts                — one line per concrete number/proper noun
  implications             — keyword+text pairs
  counterpoint              — one line caveat, empty string if none
  feasibility_observation  — ONLY if design feasibility (performance) or mass-production \
feasibility (yield) visibly changed this week, based strictly on the material below. Empty \
string if not applicable.
  changed_from_last_week   — true only if this week's judgment differs from last week's judgment \
given below
  change_note              — if changed, one line on what changed and why; empty string otherwise

Rules (hard constraints):
- Base the summary ONLY on the material given below — do not invent facts.
- Be specific: technology, companies, product/spec/capacity moves.
- No emoji, no filler like "This week's headlines show".

### Last week's judgment for {axis} (for comparison only, do not restate verbatim)
{last_week}

### This week's material for {axis} ({count} items)
{lines}

### Macro/eco notes tagged to {axis} this week
{eco_lines}
"""


def _kst_today() -> date:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Seoul")).date()
    except Exception:
        return datetime.now(timezone.utc).date()


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_eco_mapping() -> dict:
    return _load_json(ECO_MAPPING_PATH)


def _fetch_axis_items(conn, axis: str, since: date) -> list[dict]:
    """단일 축의 최근 7일치 canonical_nodes. HBM은 axis 컬럼이 아니라 태그 기준으로 전 축 검색."""
    if axis == "hbm":
        rows = conn.execute("""
            SELECT DISTINCT cn.id, cn.axis, cn.company, cn.title, cn.verification, cn.inference
            FROM raw_documents rd
            JOIN merge_log ml ON ml.raw_id = rd.id
            JOIN canonical_nodes cn ON ml.canonical_id = cn.id
            WHERE date(rd.crawled_at) >= date(?) AND ml.decision != 'noise'
        """, (since.isoformat(),)).fetchall()
    else:
        rows = conn.execute("""
            SELECT DISTINCT cn.id, cn.axis, cn.company, cn.title, cn.verification, cn.inference
            FROM raw_documents rd
            JOIN merge_log ml ON ml.raw_id = rd.id
            JOIN canonical_nodes cn ON ml.canonical_id = cn.id
            WHERE cn.axis = ? AND date(rd.crawled_at) >= date(?) AND ml.decision != 'noise'
        """, (axis, since.isoformat())).fetchall()

    items = []
    for row in rows:
        v = json.loads(row["verification"])
        inf = json.loads(row["inference"])
        tags = inf.get("tags") or []
        if axis == "hbm" and not (_HBM_TAGS & {str(t).lower() for t in tags}):
            continue
        items.append({
            "axis": row["axis"], "company": row["company"], "headline": row["title"],
            "summary": inf.get("summary") or "", "tags": tags,
            "url": v.get("url") or "", "source": v.get("source") or "",
            "published_date": v.get("published_date") or "",
        })
    return items


def _placeholder_entry(feasibility_default: str = "") -> dict:
    return {
        "executive_summary": "변화 없음", "key_facts": [], "implications": [],
        "counterpoint": "", "feasibility_observation": feasibility_default,
        "changed_from_last_week": False, "change_note": "",
    }


def _generate(by_axis: dict[str, list[dict]], eco_index: dict, mapping: dict,
              history: dict, client) -> dict:
    tag_notes = eco_client.tag_notes_since(
        eco_index, mapping.get("tag_layer", {}), since=_kst_today() - timedelta(days=6)
    )

    active = {a: items for a, items in by_axis.items() if items}
    if not active:
        return {}

    keys = list(active.keys())
    tool_schema = weekly_tool_schema(
        "weekly_axis_digest", "Weekly competitive-intelligence judgment per sector, in Korean", keys,
    )

    ko_content: dict = {}
    for axis in keys:
        items = active[axis]
        lines = "\n".join(
            f"- {it['headline']}" + (f" — {it['summary']}" if it["summary"] else "")
            for it in items[:_MAX_ITEMS_PER_AXIS]
        )
        eco_lines = "\n".join(f"- [eco] {h}" for h in eco_client.brief_note_lines(
            tag_notes.get(axis, []), limit=_MAX_ECO_LINES
        )) or "(none)"
        last_week = history.get(axis, {}).get("executive_summary") or "(기록 없음 — 이번이 첫 주)"
        anchor = _PMIC_ANCHOR if axis == "pmic" else _DEFAULT_ANCHOR

        prompt = _PROMPT_TMPL.format(
            anchor=anchor, axis=axis, last_week=last_week,
            count=len(items), lines=lines, eco_lines=eco_lines,
        )
        # 축마다 별도 호출(배치로 묶으면 프롬프트당 anchor/last_week가 달라 tool schema가 축별로
        # 갈라져야 하는데, summarize_sectors.py처럼 한 번에 묶으면 anchor 차이를 표현할 자리가 없음
        # — 축 개수가 8개뿐이라 비용 영향이 제한적이라 이 방식을 택함).
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
            tools=[weekly_tool_schema("weekly_axis_digest", "single-axis weekly digest", [axis])],
            tool_choice={"type": "tool", "name": "weekly_axis_digest"},
        )
        tool_block = next(b for b in resp.content if b.type == "tool_use")
        ko_content.update(tool_block.input)

    # PMIC: Feasibility Gate는 성숙 공정이라 상시 통과로 찍힘 — 게이트를 비우는 쪽으로 결정
    # (§8-3, "게이트를 비우거나 해당 없음 처리" 중 후자 선택. 이유는 report에 기록:
    # 구조를 다른 9축과 동일하게 유지하는 편이 렌더러/스키마 분기 없이 단순함).
    if "pmic" in ko_content:
        ko_content["pmic"]["feasibility_observation"] = "해당 없음"

    en_content = translate_weekly_batch(
        client, ko_content, "weekly_axis_digest_en", "English mirror of weekly axis digest",
    )
    return {"ko": ko_content, "en": en_content}


def run() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    today = _kst_today()
    since = today - timedelta(days=6)  # 최근 7일(오늘 포함)

    init_db()
    conn = get_conn()
    try:
        by_axis = {axis: _fetch_axis_items(conn, axis, since) for axis in AXES_ACTIVE}
    finally:
        conn.close()

    total = sum(len(v) for v in by_axis.values())
    print(f"[generate_weekly_report] {since.isoformat()}~{today.isoformat()} 수집분 {total}건 "
          f"({', '.join(f'{a}={len(v)}' for a, v in by_axis.items())})")

    mapping = _load_eco_mapping()
    eco_index = eco_client.fetch_eco_index()
    history = _load_json(HISTORY_PATH)

    ko_en: dict = {"ko": {}, "en": {}}
    if total and api_key:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            ko_en = _generate(by_axis, eco_index, mapping, history, client)
        except Exception as exc:
            print(f"::warning::generate_weekly_report 축별 생성 실패: {exc}")
    elif total:
        print("::warning::ANTHROPIC_API_KEY not set — weekly axis digest skipped")

    # 매크로 레이어(fed_policy/rates_fx/polarization) — 축 판단과 별개, 리포트 상단 1회 블록
    macro_axes = mapping.get("macro_layer", {}).get("axes", [])
    macro_notes = eco_client.macro_notes_since(eco_index, macro_axes, since)
    macro_block = {
        axis: eco_client.brief_note_lines(notes, limit=_MAX_ECO_LINES)
        for axis, notes in macro_notes.items()
    }

    # 최종 축 판단 — AXES_10 전체 자리 채움(§4 규칙1). DRAM/NAND·신호 0건 축은 placeholder.
    axis_digest = {}
    for axis in AXES_10:
        if axis in ko_en.get("ko", {}):
            axis_digest[axis] = {"ko": ko_en["ko"][axis], "en": ko_en.get("en", {}).get(axis, {})}
        else:
            default_feas = "해당 없음" if axis == "pmic" else ""
            placeholder = _placeholder_entry(default_feas)
            axis_digest[axis] = {"ko": placeholder, "en": placeholder}

    now_ts = datetime.now(timezone.utc).isoformat()
    report = {
        "week_of": since.isoformat(), "generated_through": today.isoformat(),
        "generated_at": now_ts, "macro": macro_block, "axes": axis_digest,
        "item_counts": {a: len(v) for a, v in by_axis.items()},
    }

    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    (WEEKLY_DIR / f"{today.isoformat()}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    LATEST_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # history 갱신 — 다음 주 "판단 변경" 비교용, executive_summary(ko)만 축적
    new_history = {
        axis: {"date": today.isoformat(), "executive_summary": axis_digest[axis]["ko"]["executive_summary"]}
        for axis in AXES_10
    }
    HISTORY_PATH.write_text(json.dumps(new_history, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[generate_weekly_report] axes={len(axis_digest)} → {today.isoformat()}.json, latest.json")


if __name__ == "__main__":
    sys.exit(run())
