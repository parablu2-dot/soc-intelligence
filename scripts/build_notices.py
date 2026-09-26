"""
build_notices.py — data/refined/{axis}/*.json → data/refined/notices.json

오늘의 요약 상단 "주요 공지(Notice)" 배너용. 최근 N일 신호 중 업체의 중요 이벤트를 규칙 기반으로 골라낸다.
LLM 호출 없음 — 키워드·금액 정규식 + 업체 별칭 사전만 사용 (runtime-token-zero 유지).

- 유형: strategy(전략 발표·행사·M&A) / ir(실적·가이던스·주주환원) / invest(라인·팹·설비 투자)
- 업체: 신호의 company가 추적 업체면 그대로, googlenews 등 집계 소스면 헤드라인에서 별칭 매칭
- 같은 이벤트 병합: 윈도 내 (업체, 유형) 단위로 묶어 기사 수를 점수에 반영, 행사명은 [대괄호 태그] 최빈값
- 주가·투자권유·루머 기사는 제외 (_NOISE_RE)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFINED = ROOT / "data" / "refined"
OUT_PATH = REFINED / "notices.json"

AXES = ["mobile_ap", "hpc_datacenter", "custom_soc", "foundry", "packaging"]
WINDOW_DAYS = 3
MAX_NOTICES = 10
MIN_SCORE = 5

# 업체 slug → (표시명, 별칭 정규식). 영어는 단어 경계, 한국어는 부분 일치.
COMPANIES: dict[str, tuple[str, str]] = {
    "qualcomm":        ("Qualcomm",        r"\bqualcomm\b|\bsnapdragon\b|퀄컴"),
    "apple":           ("Apple",           r"\bapple\b|애플"),
    "mediatek":        ("MediaTek",        r"\bmediatek\b|\bdimensity\b|미디어텍"),
    "unisoc":          ("Unisoc",          r"\bunisoc\b"),
    "samsung":         ("Samsung",         r"\bsamsung\b|\bexynos\b|삼성"),
    "sk_hynix":        ("SK hynix",        r"\bsk ?hynix\b|\bhynix\b|하이닉스"),
    "micron":          ("Micron",          r"\bmicron\b|마이크론"),
    "nvidia":          ("NVIDIA",          r"\bnvidia\b|엔비디아"),
    "amd":             ("AMD",             r"\bamd\b"),
    "intel":           ("Intel",           r"\bintel\b|인텔"),
    "broadcom":        ("Broadcom",        r"\bbroadcom\b|브로드컴"),
    "marvell":         ("Marvell",         r"\bmarvell\b|마벨"),
    "tsmc":            ("TSMC",            r"\btsmc\b"),
    "globalfoundries": ("GlobalFoundries", r"\bglobalfoundries\b|\bglobal foundries\b"),
    "smic":            ("SMIC",            r"\bsmic\b"),
    "ase":             ("ASE",             r"\base (?:technology|group|holdings?)\b"),
    "amkor":           ("Amkor",           r"\bamkor\b|앰코"),
    "jcet":            ("JCET",            r"\bjcet\b"),
}
# 크롤러 company slug → 위 사전의 slug (업체 크롤러 신호는 헤드라인 매칭 없이 귀속)
_CRAWLER_COMPANY = {
    "exynos": "samsung", "samsung_foundry": "samsung", "intel_foundry": "intel",
}
_COMPANY_RES = {slug: re.compile(pat, re.IGNORECASE) for slug, (_, pat) in COMPANIES.items()}

TYPE_LABEL = {"strategy": "전략 발표", "ir": "IR·실적", "invest": "라인·설비 투자"}
_TYPE_WEIGHT = {"ir": 3, "invest": 3, "strategy": 2}
# 유형 판정 우선순위 (한 헤드라인이 여러 유형에 걸리면 앞쪽 채택)
_TYPE_ORDER = ["ir", "invest", "strategy"]

_TYPE_RES = {
    "ir": re.compile(
        r"\bearnings\b|\bquarterly (?:results|revenue|profit)\b|\bq[1-4] (?:results|revenue|earnings)\b"
        r"|\bfiscal (?:q[1-4]|quarter|year)\b|\bguidance\b|\boutlook\b|\bbeats? (?:estimates|expectations)\b"
        r"|\binvestor day\b|\banalyst day\b|\bcapital markets day\b|\bdividend\b|\bbuyback\b|\bshare repurchase\b"
        r"|실적|영업이익|가이던스|어닝|컨퍼런스콜|자사주|배당",
        re.IGNORECASE),
    "invest": re.compile(
        r"\binvest(?:s|ed|ing|ment)?\b(?! (?:day|relations))|\bcapex\b|\bcapital expenditure\b"
        r"|\bnew fab\b|\bfabs?\b|\bplant\b|\bfactory\b|\bproduction line\b|\bexpand(?:s|ing)? (?:capacity|production)\b"
        r"|\b(?:capacity )?expansion\b|\bgroundbreaking\b|\bbreaks? ground\b"
        r"|투자|증설|신규 ?라인|팹|공장|착공|설비",
        re.IGNORECASE),
    "strategy": re.compile(
        r"\bsummit\b|\bkeynote\b|\broadmap\b|\bsymposium\b|\btech(?:nology)? forum\b|\bgtc\b|\bcomputex\b"
        r"|\bhot chips\b|\bunveil(?:s|ed)?\b|\bdebuts?\b|\bannounces?\b|\blaunch(?:es|ed)?\b"
        r"|\bacquir(?:e|es|ed|ing)\b|\bacquisition\b|\bmerger\b|\bstrateg(?:y|ic)\b"
        r"|로드맵|전략|공개|발표|출시|인수|합병",
        re.IGNORECASE),
}
# 가중 키워드 — 대형 행사·공식 IR·대규모 설비 (+2)
_STRONG_RE = re.compile(
    r"\bsummit\b|\bkeynote\b|\binvestor day\b|\banalyst day\b|\bgtc\b|\bsymposium\b"
    r"|\bearnings\b|\bguidance\b|\bacquisition\b|\bacquir(?:e|es|ed)\b|\bnew fab\b|\bcapex\b"
    r"|\bgroundbreaking\b|\bbreaks? ground\b|\bexpansion approved\b"
    r"|실적|가이던스|인수|착공|증설",
    re.IGNORECASE)
# 금액: $N billion / N조(원) / NT$ N billion 등 대규모 (+2)
_MONEY_RE = re.compile(
    r"\$\s?\d+(?:\.\d+)?\s?(?:billion|bn|trillion|b\b)|\d+(?:\.\d+)?\s?(?:billion|trillion) (?:dollars|usd|yen|won)"
    r"|\d+(?:\.\d+)?\s?조(?:\s?원)?",
    re.IGNORECASE)
# 주가·투자권유·루머·요약 기사 — 업체 공식 이벤트가 아니므로 제외
_NOISE_RE = re.compile(
    r"\bstocks?\b|\bshares? (?:rise|fall|jump|drop|gain|surge|slide)|\bundervalued\b|\bovervalued\b"
    r"|\bprice target\b|\bcould double\b|\bbuy (?:now|rating)\b|\bshould you\b|\bwhy is\b"
    r"|\ba \$[\d,]+ investment\b|\bleaks?\b|\btipped\b|\brumou?rs?\b|\bmost read\b|\bpatent\b"
    r"|주가|목표가|루머|유출",
    re.IGNORECASE)
_EVENT_RE = re.compile(r"^\s*\[([^\]]{2,40})\]")
# 매체 공통 말머리 — 행사명이 아님
_GENERIC_TAGS = {"news", "insights", "exclusive", "analysis", "opinion", "update", "단독", "속보", "종합", "영상", "포토"}
_SOURCE_SUFFIX_RE = re.compile(r"\s+-\s+[^-]{2,60}$")

_AGGREGATOR_SOURCES = {"googlenews", "etnews", "trendforce", "hyperscaler_inhouse"}


def _clean_headline(h: str) -> str:
    return _SOURCE_SUFFIX_RE.sub("", h or "").strip()


def _detect_company(signal: dict, text: str) -> str | None:
    """업체 크롤러 신호는 그 업체, 집계 소스는 헤드라인에서 가장 먼저 등장한 업체(=기사 주어) 1곳."""
    co = signal.get("company", "")
    co = _CRAWLER_COMPANY.get(co, co)
    if co in COMPANIES:
        return co
    hits = [(m.start(), slug) for slug, rx in _COMPANY_RES.items() if (m := rx.search(text))]
    return min(hits)[1] if hits else None


def classify(signal: dict) -> list[dict]:
    """신호 1건 → notice 후보 [dict] (주어 업체 1곳). 해당 없으면 []."""
    if signal.get("category") == "hiring":
        return []
    headline = _clean_headline(signal.get("headline", ""))
    text = headline
    ntype = next((t for t in _TYPE_ORDER if _TYPE_RES[t].search(text)), None)
    if not ntype:
        return []
    if _NOISE_RE.search(text):
        return []
    co = _detect_company(signal, text)
    if not co:
        return []
    ev = _EVENT_RE.match(headline)
    score = _TYPE_WEIGHT[ntype]
    if _STRONG_RE.search(text) or (ev and ev.group(1).strip().lower() not in _GENERIC_TAGS):
        score += 2
    if _MONEY_RE.search(text):
        score += 2
    if signal.get("company") not in _AGGREGATOR_SOURCES:
        score += 1  # 업체 공식 채널
    return [{
        "company": co,
        "type": ntype,
        "event": ev.group(1).strip() if ev and ev.group(1).strip().lower() not in _GENERIC_TAGS else "",
        "score": score,
        "headline": headline,
        "url": signal.get("url", ""),
        "source": signal.get("source", ""),
        "published_date": (signal.get("published_date") or "")[:10],
    }]


_TOKEN_RE = re.compile(r"[a-z0-9가-힣]{3,}")
_GENERIC_TOKENS = {"the", "and", "for", "with", "its", "new", "unveils", "unveil", "announces", "announce",
                   "launches", "launch", "debuts", "says", "summit", "event", "2026", "2027"}


def _representative(items: list[dict]) -> dict:
    """대표 헤드라인: 최고 점수 기사 중, 그룹 내 다른 기사들과 단어가 가장 많이 겹치는(=사건의 중심) 것."""
    best = max(i["score"] for i in items)
    # 업체명·행사명·범용 동사는 모든 기사에 공통이라 '무슨 사건인지'를 구분 못 함 → 제외
    stop = set(_TOKEN_RE.findall(" ".join(i["event"] for i in items).lower())) | _GENERIC_TOKENS
    rx = _COMPANY_RES[items[0]["company"]]
    toks = [set(t for t in _TOKEN_RE.findall(rx.sub(" ", _EVENT_RE.sub("", i["headline"])).lower()) if t not in stop)
            for i in items]
    df = Counter(t for ts in toks for t in ts)
    def centrality(k: int) -> float:
        return sum(df[t] - 1 for t in toks[k])
    cands = [k for k, i in enumerate(items) if i["score"] == best]
    return items[max(cands, key=centrality)]


def _load_signals() -> list[dict]:
    out = []
    for axis in AXES:
        d = REFINED / axis
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            if f.name == "capacity_records.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(data, list):
                out.extend(s for s in data if isinstance(s, dict) and s.get("headline"))
    return out


def build(signals: list[dict], today: date) -> dict:
    dates = [s.get("published_date", "")[:10] for s in signals if s.get("published_date")]
    dates = [d for d in dates if d <= today.isoformat()]
    end = max(dates) if dates else today.isoformat()
    start = (date.fromisoformat(end) - timedelta(days=WINDOW_DAYS - 1)).isoformat()

    groups: dict[tuple, dict] = {}
    seen: set[tuple] = set()
    for s in signals:
        d = (s.get("published_date") or "")[:10]
        if not (start <= d <= end):
            continue
        for c in classify(s):
            key_dup = (c["company"], c["headline"].lower())
            if key_dup in seen:
                continue
            seen.add(key_dup)
            g = groups.setdefault((c["company"], c["type"]), {"items": []})
            g["items"].append(c)

    notices = []
    for (co, ntype), g in groups.items():
        # 행사명 = 묶인 기사들의 [대괄호 태그] 최빈값 (없으면 빈 값)
        tags = Counter(i["event"] for i in g["items"] if i["event"])
        event = tags.most_common(1)[0][0] if tags else ""
        items = sorted(g["items"], key=lambda x: (x["score"], x["published_date"]), reverse=True)
        top = _representative(items)
        score = top["score"] + min(len(items) - 1, 4)
        if score < MIN_SCORE:
            continue
        notices.append({
            "id": f"{co}-{ntype}",
            "type": ntype,
            "type_label": TYPE_LABEL[ntype],
            "company": co,
            "company_label": COMPANIES[co][0],
            "event": event,
            "title": _EVENT_RE.sub("", top["headline"]).strip() or top["headline"],
            "count": len(items),
            "score": score,
            "date_first": min(i["published_date"] for i in items),
            "date_last": max(i["published_date"] for i in items),
            "items": [{k: i[k] for k in ("headline", "url", "source", "published_date")} for i in items[:8]],
        })
    notices.sort(key=lambda n: (n["score"], n["date_last"], n["count"]), reverse=True)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "window": {"from": start, "to": end},
        "notices": notices[:MAX_NOTICES],
    }


def run() -> None:
    result = build(_load_signals(), date.today())
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build_notices] {len(result['notices'])}건 ({result['window']['from']}~{result['window']['to']}) → {OUT_PATH}")


if __name__ == "__main__":
    sys.exit(run())
