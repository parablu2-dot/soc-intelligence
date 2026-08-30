"""
render_persona_reports.py — Weekly Report 산출물(data/refined/weekly_report/latest.json)을
페르소나별 HTML로 렌더링. 순수 템플릿팅만 수행 — LLM 호출 없음(runtime-token-zero).

3갈래 산출물 스펙(기획 §3):
  경영진(exec)  — 10축 전체 고정 5섹션 포맷 (§6)
  리더급(leader) — primary=판단·시사점 전체 / adjacent=사실 3줄만
  실무급(staff)  — 축별 신호 원문(key_facts) 나열, 판단(executive_summary/implications) 노출 안 함

색상·톤은 send_subscriber_mail.py의 기존 다크 테마를 그대로 재사용(신규 스타일 도입 안 함).
"""
from __future__ import annotations

from scripts.subscriber_schema import AXES_10

_AXIS_LABELS = {
    "mobile_ap": "Mobile AP", "hpc_datacenter": "HPC·DC", "custom_soc": "Custom SoC",
    "foundry": "Foundry", "packaging": "Packaging", "cpo_optics": "CPO/광통신",
    "dram": "DRAM", "nand": "NAND", "hbm": "HBM", "pmic": "PMIC",
}
_MACRO_LABELS = {"fed_policy": "연준/통화정책", "rates_fx": "금리/환율", "polarization": "양극화"}

_STYLE = {
    "bg": "#0d1117", "fg": "#e6edf3", "muted": "#8b949e",
    "accent": "#58a6ff", "border": "#30363d",
}


def _wrap(title: str, body: str) -> str:
    s = _STYLE
    return f"""\
<div style="font-family:-apple-system,Segoe UI,Arial,sans-serif;background:{s['bg']};color:{s['fg']};padding:20px;max-width:640px;margin:0 auto">
  <h2 style="color:{s['fg']};font-size:16px;margin-bottom:12px">{title}</h2>
  {body}
</div>"""


def _section_header(label: str) -> str:
    return f'<div style="font-size:13px;font-weight:700;color:{_STYLE["accent"]};margin:16px 0 6px">◆ {label}</div>'


def _facts_list(facts: list[str]) -> str:
    if not facts:
        return ""
    rows = "".join(f'<li style="margin-bottom:2px">{f}</li>' for f in facts)
    return f'<ul style="margin:4px 0 0 16px;padding:0;font-size:12px;line-height:1.6;color:{_STYLE["fg"]}">{rows}</ul>'


def _judgment_block(entry: dict) -> str:
    ko = entry.get("ko", {})
    facts = _facts_list(ko.get("key_facts") or [])
    implications = "".join(
        f'<div style="margin-bottom:2px"><strong>[{im["keyword"]}]</strong> {im["text"]}</div>'
        for im in ko.get("implications") or []
    )
    counterpoint = ko.get("counterpoint") or ""
    return f"""\
<div style="font-size:13px;line-height:1.6;color:{_STYLE['fg']}">{ko.get("executive_summary", "")}</div>
{facts}
{f'<div style="margin-top:4px;font-size:12px;color:{_STYLE["fg"]}">{implications}</div>' if implications else ''}
{f'<div style="margin-top:4px;font-size:11px;color:{_STYLE["muted"]}">▸ {counterpoint}</div>' if counterpoint else ''}"""


def render_exec_html(report: dict, date_str: str) -> str:
    """경영진 고정 포맷 — §6 5개 섹션, 매주 동일 순서."""
    axes = report.get("axes", {})

    # 1. 이번 주 판단 변경
    changed = [
        (a, axes[a]["ko"]) for a in AXES_10
        if axes.get(a, {}).get("ko", {}).get("changed_from_last_week")
    ]
    sec1 = (
        "".join(
            f'<div style="margin-bottom:4px;font-size:13px"><strong>{_AXIS_LABELS[a]}</strong>: {ko["change_note"]}</div>'
            for a, ko in changed
        ) if changed else f'<div style="font-size:13px;color:{_STYLE["muted"]}">변경 없음</div>'
    )

    # 2. 공통 매크로
    macro = report.get("macro", {})
    sec2 = "".join(
        f'<div style="margin-bottom:6px;font-size:13px"><strong>{_MACRO_LABELS.get(k, k)}</strong>: '
        + ("; ".join(v) if v else "변화 없음") + "</div>"
        for k, v in macro.items()
    ) or '<div style="font-size:13px;color:#8b949e">변화 없음</div>'

    # 3. 10축 현황
    sec3_rows = []
    for a in AXES_10:
        entry = axes.get(a, {}).get("ko", {})
        note = entry.get("executive_summary", "변화 없음")
        footnote = "" if a != "pmic" else ' <span style="color:#8b949e;font-size:11px">(Feasibility Gate: 해당 없음 — 성숙 공정)</span>'
        sec3_rows.append(
            f'<div style="margin-bottom:8px;font-size:13px"><strong>{_AXIS_LABELS[a]}</strong>{footnote}: {note}</div>'
        )
    sec3 = "".join(sec3_rows)

    # 4. 축 간 연결 — 이번 구현 범위에서는 항상 "없음" 고정 (임계값 미정)
    sec4 = f'<div style="font-size:13px;color:{_STYLE["muted"]}">없음</div>'

    # 5. Feasibility 관측 — "" 및 "해당 없음"(PMIC 고정값)은 "변화 있었던 항목"에서 제외
    feas = [
        (a, axes[a]["ko"]["feasibility_observation"]) for a in AXES_10
        if axes.get(a, {}).get("ko", {}).get("feasibility_observation")
        and axes[a]["ko"]["feasibility_observation"] != "해당 없음"
    ]
    sec5 = (
        "".join(f'<div style="margin-bottom:4px;font-size:13px"><strong>{_AXIS_LABELS[a]}</strong>: {obs}</div>' for a, obs in feas)
        if feas else f'<div style="font-size:13px;color:{_STYLE["muted"]}">없음</div>'
    )

    body = (
        _section_header("1. 이번 주 판단 변경") + sec1 +
        _section_header("2. 공통 매크로") + sec2 +
        _section_header("3. 10축 현황") + sec3 +
        _section_header("4. 축 간 연결") + sec4 +
        _section_header("5. Feasibility 관측") + sec5
    )
    return _wrap(f"SoC Intelligence — Weekly Report (경영진) — {date_str}", body)


def render_leader_html(report: dict, domain_scope: dict, date_str: str) -> str:
    """리더급 — primary=판단 전체, adjacent=사실 3줄만."""
    axes = report.get("axes", {})
    primary = domain_scope.get("primary", [])
    adjacent = domain_scope.get("adjacent", [])

    blocks = []
    for a in primary:
        entry = axes.get(a)
        if not entry:
            continue
        blocks.append(_section_header(f"{_AXIS_LABELS.get(a, a)} (담당)") + _judgment_block(entry))
    for a in adjacent:
        entry = axes.get(a)
        if not entry:
            continue
        facts = (entry.get("ko", {}).get("key_facts") or [])[:3]
        blocks.append(
            _section_header(f"{_AXIS_LABELS.get(a, a)} (인접 — 사실 요약만)") + _facts_list(facts or ["변화 없음"])
        )
    body = "".join(blocks) if blocks else '<div style="font-size:13px;color:#8b949e">이번 주 배정된 축 신호 없음</div>'
    return _wrap(f"SoC Intelligence — Weekly Report (리더) — {date_str}", body)


def render_staff_html(report: dict, axes_list: list[str], date_str: str) -> str:
    """실무급 — 신호 원문 요약만, 판단(executive_summary/implications) 노출 안 함."""
    axes = report.get("axes", {})
    blocks = []
    for a in axes_list:
        entry = axes.get(a)
        if not entry:
            continue
        facts = entry.get("ko", {}).get("key_facts") or []
        blocks.append(_section_header(_AXIS_LABELS.get(a, a)) + _facts_list(facts or ["이번 주 신규 신호 없음"]))
    body = "".join(blocks) if blocks else '<div style="font-size:13px;color:#8b949e">이번 주 배정된 축 신호 없음</div>'
    return _wrap(f"SoC Intelligence — Weekly Report (실무) — {date_str}", body)
