"""
tests/test_weekly_report.py — Weekly Report 생성/렌더링 단위 테스트 (Phase 3).

완료 기준(작업지시서):
  "exec-verifier 산출물이 §6 섹션 5개를 고정 배열로 출력, 빈 축이 '변화 없음'으로 남음"
  → render_exec_html의 5-섹션 구조 + placeholder 동작 검증.
  HBM은 전용 크롤러 없이 태그 기반 교차 축 집계 — _fetch_axis_items의 핵심 분기 검증.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.subscriber_schema import AXES_10
from scripts.render_persona_reports import render_exec_html, render_leader_html, render_staff_html
from scripts.generate_weekly_report import _placeholder_entry


def _fake_report() -> dict:
    axes = {}
    for a in AXES_10:
        default_feas = "해당 없음" if a == "pmic" else ""
        axes[a] = {"ko": _placeholder_entry(default_feas), "en": _placeholder_entry(default_feas)}
    axes["foundry"]["ko"] = {
        "executive_summary": "TSMC 2nm 캐파 확장 신호", "key_facts": ["N2 월 5만장 증설"],
        "implications": [], "counterpoint": "", "feasibility_observation": "양산 수율 개선 관측",
        "changed_from_last_week": True, "change_note": "지난주 '관망'에서 '확장 확인'으로 전환",
    }
    return {"week_of": "2026-08-24", "generated_through": "2026-08-30", "generated_at": "x",
            "macro": {"fed_policy": [], "rates_fx": [], "polarization": ["원/달러 3% 상승"]},
            "axes": axes, "item_counts": {}}


def test_placeholder_entry_defaults_are_empty_and_unchanged():
    p = _placeholder_entry()
    assert p["executive_summary"] == "변화 없음"
    assert p["changed_from_last_week"] is False
    assert p["feasibility_observation"] == ""


def test_pmic_placeholder_feasibility_is_na_not_empty():
    p = _placeholder_entry("해당 없음")
    assert p["feasibility_observation"] == "해당 없음"


def test_exec_html_has_all_five_sections_and_all_ten_axes():
    report = _fake_report()
    html = render_exec_html(report, "2026-08-30")
    for i in range(1, 6):
        assert f"{i}." in html
    for axis_label in ("Mobile AP", "HPC·DC", "DRAM", "NAND", "HBM", "PMIC"):
        assert axis_label in html


def test_exec_html_shows_changed_axis_in_section1_not_generic_no_change():
    report = _fake_report()
    html = render_exec_html(report, "2026-08-30")
    assert "확장 확인" in html


def test_exec_html_pmic_feasibility_excluded_from_section5_change_list():
    """PMIC의 '해당 없음'은 '변화가 생긴 항목'이 아니므로 섹션5 목록에 나열되면 안 됨."""
    report = _fake_report()
    html = render_exec_html(report, "2026-08-30")
    # foundry는 실제 feasibility 변화가 있어 섹션5에 등장해야 함
    assert "양산 수율 개선 관측" in html
    # pmic 고정값 "해당 없음"은 섹션5 변화 리스트가 아니라 섹션3의 축 현황 footnote로만 등장
    assert html.count("해당 없음") == 1  # 섹션3의 PMIC footnote 1건만


def test_leader_html_splits_primary_full_and_adjacent_facts_only():
    report = _fake_report()
    html = render_leader_html(report, {"primary": ["foundry"], "adjacent": ["packaging"]}, "2026-08-30")
    assert "TSMC 2nm 캐파 확장 신호" in html  # primary=판단 전체 노출
    assert "Packaging (인접" in html
    assert "변화 없음" in html  # adjacent(packaging)는 placeholder라 사실 없음 → "변화 없음"


def test_staff_html_never_shows_judgment_text():
    report = _fake_report()
    html = render_staff_html(report, ["foundry"], "2026-08-30")
    assert "N2 월 5만장 증설" in html          # key_facts는 노출
    assert "TSMC 2nm 캐파 확장 신호" not in html  # executive_summary(판단)는 노출 안 함


def test_hbm_axis_uses_cross_axis_tag_filter_not_axis_column():
    """HBM은 axis='hbm' 크롤러가 없으므로, 다른 축(hpc_datacenter)에 있어도 hbm 태그가 붙은
    신호만 골라내는지 확인. 태그 없는 신호는 제외되어야 함."""
    import scripts.db.db as db_mod

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tmp_db = Path(td) / "test.db"
        original_path = db_mod.DB_PATH
        db_mod.DB_PATH = tmp_db
        try:
            from scripts.db.db import get_conn, init_db, insert_raw, insert_canonical, insert_merge_log
            from scripts.generate_weekly_report import _fetch_axis_items
            from datetime import date

            init_db()
            conn = get_conn()
            now = "2026-08-30T00:00:00+00:00"

            def _add(idx: int, axis: str, title: str, tags: list[str]):
                url = f"https://example.com/{idx}"
                raw_id = f"raw{idx}"
                insert_raw(conn, {
                    "id": raw_id, "crawled_at": now, "source": "test", "axis": axis,
                    "company": "sk_hynix", "title": title, "summary": None, "url": url,
                    "raw_json": json.dumps({"tags": tags}),
                })
                insert_canonical(conn, {
                    "id": raw_id, "axis": axis, "company": "sk_hynix",
                    "entity_keys": "[]", "title": title,
                    "verification": json.dumps({"url": url, "source": "test", "published_date": "2026-08-30"}),
                    "inference": json.dumps({"tags": tags, "summary": ""}),
                    "created_at": now, "updated_at": now,
                })
                insert_merge_log(conn, {
                    "raw_id": raw_id, "canonical_id": raw_id, "similarity": None,
                    "decision": "new", "entity_match": 0, "decided_at": now,
                })

            _add(1, "hpc_datacenter", "SK hynix HBM4 mass production start", ["hbm4"])
            _add(2, "hpc_datacenter", "SK hynix Q2 earnings unrelated to HBM", [])
            _add(3, "foundry", "TSMC advanced packaging for HBM3E stacking", ["hbm3e"])
            conn.commit()

            items = _fetch_axis_items(conn, "hbm", date(2026, 8, 24))
            headlines = {it["headline"] for it in items}
            assert "SK hynix HBM4 mass production start" in headlines
            assert "TSMC advanced packaging for HBM3E stacking" in headlines
            assert "SK hynix Q2 earnings unrelated to HBM" not in headlines  # 태그 없음 → 제외

            conn.close()
        finally:
            db_mod.DB_PATH = original_path
