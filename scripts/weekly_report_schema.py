"""
weekly_report_schema.py — Weekly Report 축별 구조화 출력 스키마.

summary_schema.py(CONTENT_PROPERTIES)를 그대로 재사용하되, 경영진 고정 포맷(기획 §6)의
섹션 1(판단 변경)·섹션 5(Feasibility 관측)를 채우는 데 필요한 필드 2개를 얹는다:
  - changed_from_last_week / change_note : 지난주 judgment와 비교한 변화 여부·근거
  - feasibility_observation              : 설계·양산 타당성 변화 관측 (없으면 빈 문자열)

지난주 judgment와의 비교를 별도 알고리즘으로 만들지 않고, 이번 주 요약과 같은 배치 LLM 호출
안에서 모델이 직접 비교하게 한다(비용 추가 없음 — 어차피 이번 주 요약을 만드는 호출 1번뿐,
merge_refine.py 등 기존 스크립트와 동일하게 "빌드타임 LLM 호출"이라는 예외 안에 있음).
"""
from __future__ import annotations

import json

WEEKLY_AXIS_PROPERTIES: dict = {
    "type": "object",
    "properties": {
        "executive_summary": {
            "type": "string",
            "description": "2-3 sentence judgment summary for this axis this week. Empty string if nothing to report.",
        },
        "key_facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "One concrete fact per line (numbers, proper nouns). Empty array if none.",
        },
        "implications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string"},
                    "text": {"type": "string"},
                },
                "required": ["keyword", "text"],
                "additionalProperties": False,
            },
            "description": "Strategic implications as {keyword, text} pairs. Empty array if none.",
        },
        "counterpoint": {
            "type": "string",
            "description": "One line counterpoint or caveat. Empty string if none.",
        },
        "feasibility_observation": {
            "type": "string",
            "description": (
                "Only fill if design feasibility (performance) or mass-production feasibility "
                "(yield) showed a change this week, based strictly on given headlines. "
                "Empty string if not applicable — never fabricate a gate status."
            ),
        },
        "changed_from_last_week": {
            "type": "boolean",
            "description": "True only if this week's judgment differs from last week's judgment (given below as context).",
        },
        "change_note": {
            "type": "string",
            "description": "If changed_from_last_week is true, one line stating what changed and why. Empty string otherwise.",
        },
    },
    "required": [
        "executive_summary", "key_facts", "implications", "counterpoint",
        "feasibility_observation", "changed_from_last_week", "change_note",
    ],
    "additionalProperties": False,
}


def weekly_tool_schema(tool_name: str, description: str, keys: list[str]) -> dict:
    return {
        "name": tool_name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {k: WEEKLY_AXIS_PROPERTIES for k in keys},
            "required": keys,
            "additionalProperties": False,
        },
    }


def translate_weekly_batch(client, ko_by_key: dict, tool_name: str, description: str) -> dict:
    """summary_schema.translate_content_batch와 동일 패턴, WEEKLY_AXIS_PROPERTIES 스키마로."""
    keys = list(ko_by_key.keys())
    if not keys:
        return {}
    tool_schema = weekly_tool_schema(tool_name, description, keys)
    prompt = (
        "Translate the following structured Korean weekly summaries into English. Preserve the "
        "exact same structure and facts — do not add or omit information, translate faithfully. "
        "If a field is empty/false in the source, keep it empty/false in the translation. "
        "Do not use filler phrases.\n\n" + json.dumps(ko_by_key, ensure_ascii=False, indent=2)
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_name},
    )
    tool_block = next(b for b in resp.content if b.type == "tool_use")
    return tool_block.input
