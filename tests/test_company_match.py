"""1b googlenews 업체 태깅 — crawlers/common/company_match.py 정규식 매칭 검증."""
from crawlers.common.company_match import match_companies


def test_removed_crawler_companies_are_matched():
    assert "qualcomm" in match_companies("Qualcomm Signs Up to $60 Billion AI Chip Deal With Amazon")
    assert "broadcom" in match_companies("Broadcom's Custom-Silicon Machine Rolls On")
    assert "marvell" in match_companies("Marvell Technology Rallies On Optical Interconnect")
    assert "smic" in match_companies("SMIC profit more than triples on AI-driven chip demand")
    assert "ase" in match_companies("ASE Technology Q2 Revenue Surges Past NT$191 Billion")
    assert "amkor" in match_companies("Amkor nearly doubles investment in Peoria packaging facility")
    assert "jcet" in match_companies("JCET Reports 79.4% YoY Growth in H1 2026 Net Profit")


def test_multiple_companies_in_order():
    assert match_companies("TSMC vs Samsung Foundry: 2Q26 Share") == ["tsmc", "samsung_foundry"]


def test_short_acronyms_need_exact_case_and_word_boundary():
    # 'ase'/'amd'는 대소문자 구분 — 일반 단어·부분 문자열 오탐 방지
    assert "ase" not in match_companies("In this phase, the base case for chip demand")
    assert "amd" not in match_companies("Amdocs reports earnings")
    assert "smic" not in match_companies("seismic activity near fab")


def test_samsung_memory_news_is_not_foundry():
    assert "samsung_foundry" not in match_companies("Samsung HBM4 shipments to Nvidia begin")
    assert "samsung_foundry" in match_companies("Samsung's 2nm yield improves")


def test_empty_text():
    assert match_companies("") == []
    assert match_companies("Semiconductor stocks rally on AI demand") == []
