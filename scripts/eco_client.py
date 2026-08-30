"""
eco_client.py — eco-intelligence(별도 repo, 거시경제 8축) 읽기 전용 클라이언트.

Phase 0 확인 결과: soc-intelligence에는 eco를 읽는 코드가 전혀 없었음(신규). 접근 경로는 2가지가
실제로 존재함:
  1. 로컬 클론 `C:\\Users\\parab\\eco-intelligence` — 이 리포와 origin이 다른 별도 git repo, 로컬
     개발 중 즉시 파일시스템으로 읽을 수 있음.
  2. 공개 GitHub repo `github.com/parablu2-dot/eco-intelligence` (public) — raw.githubusercontent.com
     으로 인증 없이 fetch 가능. **GitHub Actions 러너에는 위 로컬 클론이 없으므로 이 경로가 실제
     운영(CI) 경로.**
로컬 클론이 있으면 그걸 우선 쓰고(개발 편의), 없으면 자동으로 HTTP fetch로 폴백한다 — 코드 한 벌로
로컬/CI 양쪽을 커버.

eco index.json 하나에 8축 전체 notes가 최신순으로 이미 병합되어 있어(`scripts/build-index.mjs`
산출물), 축별/날짜별 daily 파일을 개별 fetch하는 대신 index.json 1회 fetch 후 메모리에서 필터링한다
(요청 수 최소화).

fail-soft 원칙: eco 쪽 장애(네트워크, 스키마 변경)가 SOC Weekly Report 생성 전체를 죽이지 않는다 —
실패 시 빈 리스트를 반환하고 경고만 출력한다(merge_refine.py 등 기존 스크립트의 패턴과 동일).
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

_LOCAL_CLONE = Path(r"C:\Users\parab\eco-intelligence\data\index.json")
_RAW_URL = (
    "https://raw.githubusercontent.com/parablu2-dot/eco-intelligence/main/data/index.json"
)

_ECO_AXES = [
    "geopolitics", "polarization", "fed_policy", "productivity_ai",
    "us_investment", "rates_fx", "commodities_energy", "market_signals",
]


def fetch_eco_index() -> dict:
    """로컬 클론 우선, 실패 시 HTTP fetch. 둘 다 실패하면 빈 index 반환(fail-soft)."""
    if _LOCAL_CLONE.exists():
        try:
            return json.loads(_LOCAL_CLONE.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"::warning::eco_client 로컬 클론 읽기 실패({exc}) — HTTP fetch로 폴백")

    try:
        import requests
        resp = requests.get(_RAW_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        print(f"::warning::eco_client HTTP fetch 실패: {exc} — eco 레이어 없이 진행")
        return {"notes": [], "counts": {}}


def notes_for_axis_since(index: dict, axis: str, since: date) -> list[dict]:
    since_str = since.isoformat()
    return [
        n for n in index.get("notes", [])
        if n.get("axis") == axis and (n.get("date") or "") >= since_str
    ]


def macro_notes_since(index: dict, macro_axes: list[str], since: date) -> dict[str, list[dict]]:
    """공통 매크로 레이어(fed_policy/rates_fx/polarization) — 축별 최근 notes."""
    return {axis: notes_for_axis_since(index, axis, since) for axis in macro_axes}


def tag_notes_since(index: dict, tag_layer: dict[str, list[str]], since: date) -> dict[str, list[dict]]:
    """태그형 레이어 — SOC 축 slug → 해당 SOC 축에 붙는 eco notes 리스트로 뒤집어 반환.
    tag_layer는 config/eco_soc_mapping.json의 {eco_axis: [soc_axis,...]} 형태."""
    by_soc_axis: dict[str, list[dict]] = {}
    for eco_axis, soc_axes in tag_layer.items():
        notes = notes_for_axis_since(index, eco_axis, since)
        if not notes:
            continue
        for soc_axis in soc_axes:
            by_soc_axis.setdefault(soc_axis, []).extend(notes)
    return by_soc_axis


def brief_note_lines(notes: list[dict], limit: int = 5) -> list[str]:
    """LLM 프롬프트에 넣을 수 있게 headline만 짧게 추린다(원문 facts 전량 투입 금지, 비용 가드)."""
    return [n.get("headline", "") for n in notes[:limit] if n.get("headline")]
