import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_notices as bn  # noqa: E402


def _sig(headline, company="googlenews", d="2026-09-25", category="news"):
    return {"axis": "mobile_ap", "company": company, "category": category, "headline": headline,
            "url": "u", "source": "Google News", "published_date": d}


def test_classify_types():
    assert bn.classify(_sig("Micron Earnings Preview: HBM4 Ramp in Focus - X"))[0]["type"] == "ir"
    assert bn.classify(_sig("SK hynix breaks ground on $4 billion HBM plant in Indiana"))[0]["type"] == "invest"
    c = bn.classify(_sig("[Snapdragon Summit] Qualcomm Taps TSMC for All Chips - thelec.net"))[0]
    assert (c["type"], c["company"], c["event"]) == ("strategy", "qualcomm", "Snapdragon Summit")


def test_primary_company_is_first_mentioned():
    c = bn.classify(_sig("SK hynix Reportedly Explores Leasing Intel's Ohio Fab"))
    assert [x["company"] for x in c] == ["sk_hynix"]


def test_noise_and_hiring_excluded():
    assert bn.classify(_sig("TSMC Looks Undervalued as AI CapEx Keeps Climbing")) == []
    assert bn.classify(_sig("QCOM Stock Inches Higher Ahead of Snapdragon Summit")) == []
    assert bn.classify(_sig("Qualcomm hiring SoC engineers to expand fab team", category="hiring")) == []


def test_generic_bracket_tag_not_event():
    c = bn.classify(_sig("[News] Samsung Taylor Fab Fully Booked for 2nm"))[0]
    assert c["event"] == ""


def test_build_groups_and_window():
    sigs = [_sig(f"[Snapdragon Summit] Qualcomm unveils item {i}") for i in range(5)]
    sigs.append(_sig("Qualcomm unveils old chip", d="2026-09-01"))
    sigs.append(_sig("[Snapdragon Summit] Qualcomm unveils item 0"))  # 중복
    r = bn.build(sigs, date(2026, 9, 26))
    assert r["window"] == {"from": "2026-09-23", "to": "2026-09-25"}
    assert len(r["notices"]) == 1
    n = r["notices"][0]
    assert (n["company"], n["type"], n["count"], n["event"]) == ("qualcomm", "strategy", 5, "Snapdragon Summit")


def test_low_score_single_article_dropped():
    r = bn.build([_sig("Intel launches new driver")], date(2026, 9, 26))
    assert r["notices"] == []
