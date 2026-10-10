import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_judgments as bj  # noqa: E402

GOOD = """---
id: J-20261010-001
date: 2026-10-10
axis: cpo_optics
topic: "q"
judgment: "j"
direction: 신규
evidence:
  - source: "S"
    url: "https://news.google.com/a"
    claim: "c"
    role: 지지
    note: "1차 출처 메모"
  - source: "T"
    url: "https://other/b"
    headline: "Headline B - T"
    claim: "c2"
    role: 반증
  - source: "X"
    url: "https://nowhere"
    claim: "c3"
    role: 지지
confidence: 0.7
prediction: "p"
check_date: 2027-03-31
outcome: null
lesson: null
supersedes: null
---
"""


def _setup(tmp_path, monkeypatch, files: dict, signals=None):
    src = tmp_path / "data" / "judgments"
    src.mkdir(parents=True)
    for name, text in files.items():
        (src / name).write_text(text, encoding="utf-8")
    refined = tmp_path / "data" / "refined"
    (refined / "cpo_optics").mkdir(parents=True)
    (refined / "cpo_optics" / "googlenews.json").write_text(json.dumps(signals or [
        {"headline": "Headline A - S", "url": "https://news.google.com/a", "source": "S", "company": "googlenews"},
        {"headline": "Headline B - T", "url": "https://news.google.com/b", "source": "T", "company": "googlenews"},
        {"headline": "Headline C", "url": "https://ecoc/c", "source": "ECOC", "company": "ecoc"},
    ]), encoding="utf-8")
    (refined / "cpo_optics" / "digest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bj, "ROOT", tmp_path)
    monkeypatch.setattr(bj, "SRC_DIR", src)
    monkeypatch.setattr(bj, "REFINED", refined)


def test_valid_record_dates_serialized_and_evidence_linked(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"J-20261010-001.md": GOOD})
    out = bj.build(today="2026-10-10")
    assert out["errors"] == [] and out["count"] == 1
    r = out["judgments"][0]
    assert r["date"] == "2026-10-10" and r["check_date"] == "2027-03-31"
    ev = r["evidence"]
    assert ev[0]["matched"]["match"] == "url" and ev[0]["note"] == "1차 출처 메모"
    assert ev[1]["matched"]["match"] == "headline"  # url 불일치 → headline fallback
    assert ev[2]["matched"] is None
    assert out["coverage"]["cpo_optics"] == {"total": 3, "top_source": "googlenews", "top_count": 2, "top_pct": 67}
    json.dumps(out)  # date 객체가 남아 있지 않아야 함


def test_error_record_excluded_but_reported(tmp_path, monkeypatch):
    bad = GOOD.replace("J-20261010-001", "J-20261011-001").replace("axis: cpo_optics", "axis: cpo")
    _setup(tmp_path, monkeypatch, {"J-20261010-001.md": GOOD, "J-20261011-001.md": bad})
    out = bj.build(today="2026-10-12")
    assert [r["id"] for r in out["judgments"]] == ["J-20261010-001"]  # 이전 정상 판단 유지
    assert any("axis 'cpo'" in e for e in out["errors"])
    assert out["blocked"] == {}  # axis 자체가 잘못되면 어느 축에 보류 표시할지 모름 → 전역 오류 배지만


def test_blocked_marks_axis_of_excluded_newer_judgment(tmp_path, monkeypatch):
    bad = GOOD.replace("J-20261010-001", "J-20261011-001").replace("direction: 신규", "direction: 상승")
    _setup(tmp_path, monkeypatch, {"a.md": GOOD, "b.md": bad})
    out = bj.build(today="2026-10-12")
    assert [r["id"] for r in out["judgments"]] == ["J-20261010-001"]
    assert out["blocked"] == {"cpo_optics": ["J-20261011-001"]}


def test_evidence_required_for_domain_axis_only(tmp_path, monkeypatch):
    no_ev = GOOD.split("evidence:")[0] + "confidence:" + GOOD.split("confidence:")[1]
    meta = no_ev.replace("J-20261010-001", "J-20261010-002").replace("axis: cpo_optics", "axis: meta")
    _setup(tmp_path, monkeypatch, {"a.md": no_ev, "b.md": meta})
    out = bj.build(today="2026-10-10")
    assert [r["id"] for r in out["judgments"]] == ["J-20261010-002"]
    assert any("evidence 필수" in e for e in out["errors"])


def test_unknown_fields_and_enums_rejected(tmp_path, monkeypatch):
    bad = (GOOD.replace("direction: 신규", "direction: 상승")
               .replace("role: 반증", "role: 중립")
               .replace("    note:", "    memo:"))
    _setup(tmp_path, monkeypatch, {"a.md": bad})
    out = bj.build(today="2026-10-10")
    assert out["count"] == 0
    joined = " ".join(out["errors"])
    assert "direction '상승'" in joined and "role '중립'" in joined and "스키마 밖 필드 ['memo']" in joined


def test_duplicate_ids_and_yaml_error(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"a.md": GOOD, "b.md": GOOD, "c.md": "---\nid: [\n---\n"})
    out = bj.build(today="2026-10-10")
    assert out["count"] == 0
    assert any("중복 id" in e for e in out["errors"]) and any("YAML 오류" in e for e in out["errors"])


def test_outcome_stats_by_axis_and_overdue(tmp_path, monkeypatch):
    hit = GOOD.replace("outcome: null", "outcome: hit")
    meta = (GOOD.replace("J-20261010-001", "J-20261010-002").replace("axis: cpo_optics", "axis: meta")
                .replace("check_date: 2027-03-31", "check_date: 2026-11-01"))
    _setup(tmp_path, monkeypatch, {"a.md": hit, "b.md": meta})
    out = bj.build(today="2026-11-02")
    assert out["outcome_stats"]["by_axis"] == {"cpo_optics": {"hit": 1, "miss": 0, "partial": 0},
                                               "meta": {"hit": 0, "miss": 0, "partial": 0}}
    assert out["overdue_checks"] == ["J-20261010-002"]


def test_ci_flag_exit_code(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, {"a.md": GOOD.replace("confidence: 0.7", "confidence: 7")})
    monkeypatch.setattr(bj, "OUT", tmp_path / "data" / "refined" / "judgments.json")
    summary = tmp_path / "summary.md"
    monkeypatch.setattr(bj.os, "environ", {"GITHUB_STEP_SUMMARY": str(summary)})
    assert bj.main([]) == 1
    assert not summary.exists()  # 로컬 실행은 CI 주석 없음
    assert bj.main(["--ci"]) == 0
    assert json.loads(bj.OUT.read_text(encoding="utf-8"))["errors"]
    assert "판단 기록 오류 1건" in summary.read_text(encoding="utf-8")


def test_axes_match_crawler_axes():
    src = (Path(__file__).resolve().parents[1] / "crawlers" / "run_all.py").read_text(encoding="utf-8")
    for a in bj.SIGNAL_AXES:
        assert f'"{a}"' in src
