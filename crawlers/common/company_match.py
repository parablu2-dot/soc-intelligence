"""
company_match.py — aggregator(googlenews) 신호의 헤드라인·요약에서 언급 업체 슬러그를 추출 (1b 업체 태깅).

googlenews 신호는 company='googlenews' 고정 — dedup_gate의 axis+company 스코프를 건드리지 않도록
company는 그대로 두고, export_refined.py가 별도 필드 mentions(슬러그 리스트)로 부착한다.
site/js/app.js의 업체별 뷰(생태계 그래프·업체별 주요 전략)는 company 또는 mentions로 매칭.

LLM 없이 정규식만 사용 (런타임 토큰 0 원칙). 슬러그는 app.js AXIS_COMPANIES와 동일해야 한다.
오탐이 비싼 짧은 약어(ASE, AMD, GF)는 대소문자 구분 + 단어 경계로만 매칭.
"""
import re

_I = re.IGNORECASE

# 슬러그 → [(패턴, 플래그)] — 하나라도 맞으면 언급으로 판정
_COMPANY_PATTERNS: dict[str, list[tuple[str, int]]] = {
    # Mobile AP
    "apple":           [(r"\bApple\b", 0), (r"\biPhone\b", _I), (r"\bA\d{2} (?:Pro|Bionic)\b", 0), (r"\bM[1-9] (?:Pro|Max|Ultra)\b", 0), (r"苹果", 0)],
    "qualcomm":        [(r"\bQualcomm\b", _I), (r"\bSnapdragon\b", _I), (r"高通", 0)],
    "mediatek":        [(r"\bMediaTek\b", _I), (r"\bDimensity\b", _I), (r"联发科|聯發科", 0)],
    "unisoc":          [(r"\bUnisoc\b", _I), (r"紫光展锐", 0)],
    "exynos":          [(r"\bExynos\b", _I)],
    # HPC·Datacenter
    "nvidia":          [(r"\bNvidia\b", _I), (r"英伟达|輝達", 0)],
    "amd":             [(r"\bAMD\b", 0), (r"\bInstinct MI\d", _I), (r"\bEPYC\b", _I)],
    "intel":           [(r"\bIntel\b", _I), (r"英特尔", 0)],
    # Custom SoC
    "broadcom":        [(r"\bBroadcom\b", _I), (r"博通", 0)],
    "marvell":         [(r"\bMarvell\b", _I)],
    "hyperscaler_inhouse": [(r"\bTrainium\d?\b", _I), (r"\bInferentia\b", _I), (r"\bGraviton\d?\b", _I),
                            (r"\bMaia\b", 0), (r"\bMTIA\b", 0), (r"\bAxion\b", 0), (r"\bCobalt \d", 0),
                            (r"\bGoogle TPU|\bTPU ?v\d|\bIronwood\b", _I)],
    # Foundry
    "tsmc":            [(r"\bTSMC\b", _I), (r"Taiwan Semiconductor Manufacturing", _I), (r"台积电|台積電", 0)],
    "samsung_foundry": [(r"\bSamsung Foundry\b", _I), (r"\bSamsung(?:'s)? (?:\d ?nm|SF\d|GAA|foundry)", _I), (r"三星晶圆代工", 0)],
    "intel_foundry":   [(r"\bIntel Foundry\b", _I), (r"\bIntel(?:'s)? (?:18A|14A)\b", _I), (r"\bIFS\b", 0)],
    "globalfoundries": [(r"\bGlobalFoundries\b", _I), (r"格芯", 0)],
    "smic":            [(r"\bSMIC\b", 0), (r"中芯国际|中芯", 0)],
    # Packaging
    "ase":             [(r"\bASE (?:Technology|Group|Holding)\b", _I), (r"\bASE\b", 0), (r"日月光", 0)],
    "amkor":           [(r"\bAmkor\b", _I)],
    "jcet":            [(r"\bJCET\b", _I), (r"长电科技", 0)],
}

_COMPILED = {
    slug: [re.compile(p, f) for p, f in pats] for slug, pats in _COMPANY_PATTERNS.items()
}


def match_companies(text: str) -> list[str]:
    """텍스트에서 언급된 업체 슬러그 목록 (정의 순서, 중복 없음)."""
    if not text:
        return []
    return [slug for slug, pats in _COMPILED.items() if any(p.search(text) for p in pats)]
