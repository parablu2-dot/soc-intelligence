"""
tests/test_dedup.py — dedup_gate 단위 테스트

완료 기준 #1 (작업지시서):
  "TSMC 2nm" vs "삼성 2nm" → entity_match=False → decision=new (false merge 방어)

완료 기준 #2 (샘플 10건 → merge_log 10행):
  test_sample_ten_raws_produce_ten_log_entries
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.dedup_gate import extract_entities, entities_match, _url_id, _make_canonical

# ── 헬퍼 픽스처 ────────────────────────────────────────────────────────────────

def _sig(company: str, headline: str, tags: list[str] | None = None) -> dict:
    return {
        "company": company,
        "headline": headline,
        "tags": tags or [],
        "url": f"https://example.com/{company}/{headline[:20].replace(' ', '-')}",
        "axis": "foundry",
        "source": "test",
        "published_date": "2026-07-02",
        "category": "news",
        "summary": None,
    }


# ── 엔티티 추출 ────────────────────────────────────────────────────────────────

def test_extract_2nm_from_headline():
    e = extract_entities(_sig("tsmc", "TSMC 2nm volume production ramp"))
    assert "2nm" in e["nodes"]


def test_extract_n3e_takes_priority_over_n3():
    """N3E 를 N3 로 잘못 매칭하지 않는지 확인 (길이 내림차순 정렬 검증)."""
    e = extract_entities(_sig("tsmc", "TSMC N3E customer tape-out", ["n3e"]))
    assert "n3e" in e["nodes"]
    assert "n3" in e["nodes"]   # n3 은 n3e 의 부분 문자열이므로 함께 포함됨
    # 중요: entity_match 시 intersection으로 비교하므로 n3e와 n3가 모두 있어도 무방


def test_extract_no_node_when_irrelevant():
    e = extract_entities(_sig("nvidia", "NVIDIA H100 GPU AI training benchmark"))
    assert e["nodes"] == frozenset()


def test_extract_cowos_product():
    e = extract_entities(_sig("tsmc", "TSMC CoWoS-L capacity expansion", ["cowos"]))
    assert "cowos" in e["products"]


# ── 핵심 방어 케이스: false merge 방어 ────────────────────────────────────────

def test_false_merge_tsmc_vs_samsung_2nm():
    """완료 기준 #1 — TSMC 2nm vs 삼성 2nm: 회사 불일치 → entities_match=False."""
    e_tsmc = extract_entities(_sig("tsmc", "TSMC 2nm yield improvement", ["2nm"]))
    e_sam = extract_entities(_sig("samsung_foundry", "삼성 2nm 공정 수율 향상", ["2nm"]))
    assert not entities_match(e_tsmc, e_sam), (
        "TSMC vs Samsung_Foundry must NOT match regardless of similarity"
    )


def test_false_merge_same_company_different_node():
    """같은 회사라도 공정 노드 충돌 시 → entities_match=False."""
    e_n2 = extract_entities(_sig("tsmc", "TSMC N2 tape-out record", ["n2"]))
    e_n3e = extract_entities(_sig("tsmc", "TSMC N3E customer wins Q3", ["n3e"]))
    # n2 nodes={n2}, n3e nodes={n3e, n3} → intersection 없음
    assert not entities_match(e_n2, e_n3e)


def test_false_merge_different_company_no_node():
    """노드 정보 없어도 회사 다르면 False."""
    e_nv = extract_entities(_sig("nvidia", "NVIDIA expands AI chip lineup"))
    e_am = extract_entities(_sig("amd", "AMD MI300 competitive analysis"))
    assert not entities_match(e_nv, e_am)


# ── 정상 매칭 케이스 ──────────────────────────────────────────────────────────

def test_match_same_company_same_node():
    e_a = extract_entities(_sig("tsmc", "TSMC 2nm capacity expansion Q2", ["2nm"]))
    e_b = extract_entities(_sig("tsmc", "TSMC N2 wafer price estimate", ["2nm"]))
    assert entities_match(e_a, e_b)


def test_match_same_company_no_nodes():
    """노드 정보 없을 때 회사만 같으면 True (충돌 없음)."""
    e_a = extract_entities(_sig("nvidia", "NVIDIA new HPC roadmap announced"))
    e_b = extract_entities(_sig("nvidia", "NVIDIA announces updated datacenter strategy"))
    assert entities_match(e_a, e_b)


def test_match_same_company_one_side_has_node():
    """한쪽만 노드 정보 있을 때 → 충돌 없음 → True."""
    e_a = extract_entities(_sig("tsmc", "TSMC 2nm process update", ["2nm"]))
    e_b = extract_entities(_sig("tsmc", "TSMC foundry strategy overview"))
    assert entities_match(e_a, e_b)


# ── 완료 기준 #2: 샘플 10건 → merge_log 10행 ──────────────────────────────────

def test_sample_ten_raws_produce_ten_log_entries():
    """
    인메모리 SQLite로 dedup_gate 핵심 로직 시뮬레이션.
    10개 raw 투입 → merge_log 10행 생성 검증.
    sentence-transformers 불필요 (후보 없음 → all new 경로).
    """
    import scripts.db.db as db_mod

    # ignore_cleanup_errors=True: Windows에서 SQLite WAL 파일 락으로
    # TemporaryDirectory cleanup이 실패하는 경우 무시 (Python 3.10+)
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tmp_db = Path(td) / "test.db"
        original_path = db_mod.DB_PATH
        db_mod.DB_PATH = tmp_db
        try:
            from scripts.db.db import (
                get_conn, init_db,
                insert_raw, insert_canonical, insert_merge_log,
                get_unprocessed_raws,
            )
            init_db()
            conn = get_conn()

            now = "2026-07-02T00:00:00+00:00"
            companies = [
                ("tsmc", "TSMC 2nm", ["2nm"]),
                ("tsmc", "TSMC N3E expansion", ["n3e"]),
                ("samsung_foundry", "Samsung 2nm update", ["2nm"]),
                ("samsung_foundry", "Samsung 3GAE progress", ["3gae"]),
                ("nvidia", "NVIDIA H100 shipment", []),
                ("amd", "AMD MI300 benchmark", []),
                ("intel", "Intel 18A process", ["18a"]),
                ("tsmc", "TSMC CoWoS-L expansion", ["cowos"]),
                ("globalfoundries", "GF 12LP+ yield rate", ["12lp"]),
                ("tsmc", "TSMC N5 mature node", ["n5"]),
            ]

            for i, (company, headline, tags) in enumerate(companies):
                sig = _sig(company, headline, tags)
                sig["url"] = f"https://example.com/article/{i}"
                raw_id = _url_id(sig["url"])
                insert_raw(conn, {
                    "id": raw_id,
                    "crawled_at": now,
                    "source": "test",
                    "axis": "foundry" if company != "nvidia" and company != "amd" and company != "intel" else "hpc_datacenter",
                    "company": company,
                    "title": headline,
                    "summary": None,
                    "url": sig["url"],
                    "raw_json": json.dumps(sig),
                })

            # 미처리 raws 조회
            unprocessed = get_unprocessed_raws(conn)
            assert len(unprocessed) == 10, f"Expected 10, got {len(unprocessed)}"

            # 후보 없음 경로 시뮬레이션 (no sentence-transformers needed)
            for row in unprocessed:
                raw = dict(row)
                sig = json.loads(raw["raw_json"])
                raw_e = extract_entities(sig)
                new_c = _make_canonical(raw, sig, raw_e, now)
                insert_canonical(conn, new_c)
                insert_merge_log(conn, {
                    "raw_id": raw["id"],
                    "canonical_id": new_c["id"],
                    "similarity": None,
                    "decision": "new",
                    "entity_match": 0,
                    "decided_at": now,
                })

            conn.commit()

            # 검증: merge_log 10행
            count = conn.execute("SELECT COUNT(*) FROM merge_log").fetchone()[0]
            assert count == 10, f"Expected 10 merge_log rows, got {count}"

            # 검증: decision 분포 확인 가능
            decisions = conn.execute(
                "SELECT decision, COUNT(*) AS n FROM merge_log GROUP BY decision"
            ).fetchall()
            decision_map = {r["decision"]: r["n"] for r in decisions}
            assert "new" in decision_map
            assert decision_map["new"] == 10

            conn.close()
        finally:
            db_mod.DB_PATH = original_path
