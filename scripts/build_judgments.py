#!/usr/bin/env python3
"""
build_judgments.py — data/judgments/J-*.md frontmatter → data/refined/judgments.json

Judgment Schema V1 (Judgment UX 파일럿 메모 v6, 2026-10-10). 10/2 판단기록시스템 build_judgments.py 재사용
— 필수 필드 검증·중복 id·supersedes 계보·overdue_checks·outcome_stats 유지, 아래를 추가:

- axis 필수 enum(신호 axis 체계 + meta) / direction enum / evidence 구조 검사(axis != meta면 1건 이상 필수)
- evidence[].url(정확 일치) → headline(정확 일치) 순으로 같은 axis의 기존 신호와 연결 (claim은 매칭에 안 씀)
- evidence[].note: 선택 필드(1차 출처·Red Team 메모) — 화면에서 각주로 표시 (2026-10-10 결정)
- 오류 레코드는 errors[]에만 남기고 judgments(렌더 대상)에서 제외 → 이전 정상 판단이 계속 렌더됨
- outcome_stats는 axis별 분리 집계 (total은 참고값)
- coverage: 판단이 있는 축별 신호 N건 · 최다 소스 비율 (빌드마다 계산, 상수 금지)
- --ci: 검증 오류가 있어도 exit 0 (그날 크롤링 커밋을 막지 않음). 오류는 JSON errors[] → 화면 경고 배지.
  로컬 실행(옵션 없음)은 오류 시 exit 1.

원본(Source of Truth)은 md frontmatter(append-only). 결과물은 손으로 고치지 않는다. LLM 호출 없음.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "data" / "judgments"
REFINED = ROOT / "data" / "refined"
OUT = REFINED / "judgments.json"

KST = timezone(timedelta(hours=9))

# 신호 axis 체계(crawlers/run_all.py _CRAWLER_AXES)와 동일 + meta. app.js 모듈 id('cpo')와 혼동 금지.
SIGNAL_AXES = ["mobile_ap", "hpc_datacenter", "custom_soc", "foundry", "packaging", "cpo_optics", "pmic"]
AXES = SIGNAL_AXES + ["meta"]
DIRECTIONS = ["강화", "약화", "유지", "신규"]
OUTCOMES = ["hit", "miss", "partial"]
ROLES = ["지지", "반증"]

REQUIRED = ["id", "date", "axis", "topic", "judgment", "confidence", "prediction", "check_date"]
FIELDS = REQUIRED + ["direction", "evidence", "rationale", "verified_by", "outcome", "lesson",
                     "supersedes", "verifier_checks"]
EVIDENCE_REQUIRED = ["source", "url", "claim", "role"]
EVIDENCE_FIELDS = EVIDENCE_REQUIRED + ["headline", "note"]
# 2차(Verifier 화면)용 자리 확보 — 1차에선 값 검사만
VERIFIER_CHECKS = ["Source Quality", "Temporal Validity", "Claim-Evidence Traceability",
                   "Counterevidence", "Missing Evidence", "Confidence"]

ID_RE = re.compile(r"^J-\d{8}-\d{3}$")


def _plain(v):
    """yaml이 date 객체로 읽은 값을 중첩 구조까지 ISO 문자열로."""
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def read_frontmatter(path: Path):
    """(record | None, error | None). 판단 기록이 아닌 일반 노트는 (None, None)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None, None
    try:
        fm = yaml.safe_load(text.split("---", 2)[1])
    except yaml.YAMLError as e:
        # 10/2 원본은 WARN 후 건너뛰었지만, CI에서 조용히 사라지지 않도록 오류로 기록
        return None, f"{path.name}: YAML 오류 ({e})"
    if not isinstance(fm, dict) or not str(fm.get("id", "")).startswith("J-"):
        return None, None
    fm = _plain(fm)
    fm["source_file"] = path.relative_to(ROOT).as_posix()
    return fm, None


def validate(fm: dict) -> list[str]:
    """레코드 1건 검증 → 오류 메시지 목록 (비어 있으면 정상)."""
    rid = fm.get("id")
    errs = []
    missing = [k for k in REQUIRED if fm.get(k) in (None, "")]
    if missing:
        errs.append(f"필수 필드 누락 {missing}")
    unknown = [k for k in fm if k not in FIELDS and k != "source_file"]
    if unknown:
        errs.append(f"스키마 밖 필드 {unknown}")
    if not ID_RE.match(str(rid)):
        errs.append(f"id 형식 오류 '{rid}' (J-yyyymmdd-nnn)")
    axis = fm.get("axis")
    if axis not in (None, "") and axis not in AXES:
        errs.append(f"axis '{axis}' 는 {AXES} 중 하나여야 함")
    if fm.get("direction") not in (None, "") and fm["direction"] not in DIRECTIONS:
        errs.append(f"direction '{fm['direction']}' 는 {DIRECTIONS} 중 하나여야 함")
    if fm.get("outcome") not in (None, "") and fm["outcome"] not in OUTCOMES:
        errs.append(f"outcome '{fm['outcome']}' 는 {OUTCOMES} 또는 null")
    conf = fm.get("confidence")
    if conf not in (None, "") and (isinstance(conf, bool) or not isinstance(conf, (int, float)) or not 0 <= conf <= 1):
        errs.append(f"confidence '{conf}' 는 0~1 숫자")
    for k in ("date", "check_date"):
        v = fm.get(k)
        if v not in (None, ""):
            try:
                date.fromisoformat(str(v))
            except ValueError:
                errs.append(f"{k} '{v}' 날짜 형식 오류 (yyyy-mm-dd)")
    checks = fm.get("verifier_checks")
    if checks not in (None, ""):
        bad = [c for c in (checks if isinstance(checks, list) else [checks]) if c not in VERIFIER_CHECKS]
        if bad:
            errs.append(f"verifier_checks 값 {bad} 는 {VERIFIER_CHECKS} 중 하나여야 함")

    # evidence: 도메인 축은 필수(1건 이상), meta는 선택 (천 결정 2026-10-10)
    ev = fm.get("evidence")
    if ev in (None, "", []):
        if axis in SIGNAL_AXES:
            errs.append(f"evidence 필수 (axis={axis}, 1건 이상)")
    elif not isinstance(ev, list):
        errs.append("evidence 는 목록이어야 함")
    else:
        for i, e in enumerate(ev):
            if not isinstance(e, dict):
                errs.append(f"evidence[{i}] 는 매핑이어야 함")
                continue
            miss = [k for k in EVIDENCE_REQUIRED if e.get(k) in (None, "")]
            if miss:
                errs.append(f"evidence[{i}] 필수 필드 누락 {miss}")
            extra = [k for k in e if k not in EVIDENCE_FIELDS]
            if extra:
                errs.append(f"evidence[{i}] 스키마 밖 필드 {extra}")
            if e.get("role") not in (None, "") and e["role"] not in ROLES:
                errs.append(f"evidence[{i}].role '{e['role']}' 는 {ROLES} 중 하나여야 함")
    return [f"{rid or fm.get('source_file')}: {m}" for m in errs]


def load_signals(axis: str) -> list[dict]:
    """data/refined/{axis}/*.json 신호 합본 (digest 등 신호 목록이 아닌 파일은 건너뜀)."""
    out = []
    for f in sorted((REFINED / axis).glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, list):
            out.extend(s for s in data if isinstance(s, dict) and s.get("headline"))
    return out


def link_evidence(record: dict, signals: list[dict]) -> None:
    """evidence[] 각 항목에 같은 axis 신호를 url → headline 정확 일치로 연결 (matched 필드)."""
    by_url = {s["url"]: s for s in signals if s.get("url")}
    by_headline = {s["headline"]: s for s in signals}
    for e in record.get("evidence") or []:
        sig, how = by_url.get(e.get("url")), "url"
        if sig is None and e.get("headline"):
            sig, how = by_headline.get(e["headline"]), "headline"
        e["matched"] = None if sig is None else {
            "match": how,
            "headline": sig.get("headline"),
            "source": sig.get("source"),
            "company": sig.get("company"),
            "published_date": sig.get("published_date"),
            "url": sig.get("url"),
        }


def coverage(signals: list[dict]) -> dict | None:
    """헤더 배지: N건 · 최다 소스(company) 비율 %."""
    if not signals:
        return None
    top, cnt = Counter(s.get("company") or "unknown" for s in signals).most_common(1)[0]
    return {"total": len(signals), "top_source": top, "top_count": cnt,
            "top_pct": round(cnt * 100 / len(signals))}


def outcome_counts(records: list[dict]) -> dict:
    return {k: sum(r.get("outcome") == k for r in records) for k in OUTCOMES}


def build(today: str | None = None) -> dict:
    today = today or datetime.now(KST).date().isoformat()
    candidates, errors = [], []
    for md in sorted(SRC_DIR.rglob("*.md")) if SRC_DIR.exists() else []:
        fm, err = read_frontmatter(md)
        if err:
            errors.append(err)
        if fm is not None:
            candidates.append(fm)

    ids = [r["id"] for r in candidates]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errors.append(f"중복 id: {sorted(dup)}")

    # 오류 레코드는 렌더 대상에서 제외 (중복 id는 해당 id 전부 제외 — 어느 쪽이 원본인지 모름)
    records = []
    for fm in candidates:
        errs = validate(fm)
        errors.extend(errs)
        if not errs and fm["id"] not in dup:
            records.append(fm)
    records.sort(key=lambda r: (str(r["date"]), r["id"]))

    signals_cache = {}
    for r in records:
        if r["axis"] in SIGNAL_AXES:
            sigs = signals_cache.setdefault(r["axis"], load_signals(r["axis"]))
            link_evidence(r, sigs)

    # Outcome check 대상: 검증일이 지났는데 outcome이 비어 있는 판단
    overdue = [r["id"] for r in records if not r.get("outcome") and str(r["check_date"]) <= today]
    # Historian용: supersedes 체인 (새 판단 → 이전 판단)
    lineage = {r["id"]: r["supersedes"] for r in records if r.get("supersedes")}
    # Learner용: axis별 적중 집계 (meta UX 가설과 도메인 판단이 한 숫자로 섞이지 않게)
    by_axis = {a: outcome_counts([r for r in records if r["axis"] == a])
               for a in sorted({r["axis"] for r in records})}

    return {
        "generated": today,
        "count": len(records),
        "outcome_stats": {"by_axis": by_axis, "total": outcome_counts(records)},
        "overdue_checks": overdue,
        "lineage": lineage,
        "coverage": {a: coverage(s) for a, s in signals_cache.items()},
        "errors": errors,
        "judgments": records,
    }


def main(argv: list[str]) -> int:
    ci = "--ci" in argv
    result = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[OK] {result['count']}건 → {OUT.relative_to(ROOT).as_posix()} | "
          f"검증 대기 {len(result['overdue_checks'])}건 | 오류 {len(result['errors'])}건")
    for e in result["errors"]:
        print(f"[ERR] {e}")
    return 0 if ci or not result["errors"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
