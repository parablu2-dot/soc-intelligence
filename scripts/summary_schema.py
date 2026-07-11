"""
summary_schema.py — A-2 통일 구조화 요약 스키마 (executive_summary/key_facts/implications/counterpoint).

sector_summaries·distillation_summaries 공용 (두 소비처가 동일 구조를 요구하므로 공유).
baseline note는 통합 대상에서 제외 — 장문 수기 리서치 문서라 LLM 미개입 원칙 유지(CLAUDE.md 참고).
"""
from __future__ import annotations

import json

CONTENT_PROPERTIES: dict = {
    "type": "object",
    "properties": {
        "executive_summary": {
            "type": "string",
            "description": "2-3 sentence executive summary. Use the empty string if there is nothing to report.",
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
    },
    "required": ["executive_summary", "key_facts", "implications", "counterpoint"],
    "additionalProperties": False,
}


def content_tool_schema(tool_name: str, description: str, keys: list[str]) -> dict:
    """keys(축/카테고리 등) 각각에 CONTENT_PROPERTIES 구조를 요구하는 tool schema 조립."""
    return {
        "name": tool_name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {k: CONTENT_PROPERTIES for k in keys},
            "required": keys,
            "additionalProperties": False,
        },
    }


_TRANSLATE_PROMPT_TMPL = """\
Translate the following structured Korean summaries into English. Preserve the exact same structure \
and facts — do not add or omit information, translate faithfully. If a field is empty in the source, \
keep it empty in the translation. Do not use filler phrases.

{payload}
"""


def translate_content_batch(client, ko_by_key: dict, tool_name: str, description: str) -> dict:
    """KO 구조화 content dict → EN 구조화 content dict로 미러링(단일 배치 호출, 선생성·커밋)."""
    keys = list(ko_by_key.keys())
    if not keys:
        return {}
    tool_schema = content_tool_schema(tool_name, description, keys)
    prompt = _TRANSLATE_PROMPT_TMPL.format(payload=json.dumps(ko_by_key, ensure_ascii=False, indent=2))
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": tool_name},
    )
    tool_block = next(b for b in resp.content if b.type == "tool_use")
    return tool_block.input
