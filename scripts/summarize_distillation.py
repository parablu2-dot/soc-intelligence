"""
summarize_distillation.py — 1차 증류(리뷰 큐 판단 메모)를 축·카테고리별로 빌드타임 LLM 요약.

입력: data/distillation_notes.json
      (프론트 "일일 리뷰 큐" 모듈의 "메모 내보내기" 버튼으로 다운로드한 파일을
       사용자가 수동으로 이 경로에 커밋해야 함 — 브라우저 localStorage는
       빌드 파이프라인이 직접 읽을 수 없음)
출력: data/refined/distillation_summaries.json

LLM 역할: 메모에 없는 사실 추가 금지, 메모 종합만 수행 (merge_refine.py와 동일한
          "유일한 LLM 호출 지점" 원칙 아래 별도 호출 — 입력 파일 없으면 스킵)
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_NOTES_PATH = ROOT / "data" / "distillation_notes.json"
_OUT_PATH = ROOT / "data" / "refined" / "distillation_summaries.json"

_TOOL: dict = {
    "name": "category_summary",
    "description": "Summarize analyst review notes for one axis/category into a concise brief",
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": "2-3 sentence synthesis of the analyst notes, written in Korean",
            },
        },
        "required": ["summary"],
        "additionalProperties": False,
    },
}

_PROMPT_TMPL = """\
다음은 SoC 경쟁 인텔리전스 분석가가 남긴 1차 증류(판단 메모)입니다.
축: {axis} / 카테고리: {category}

메모 (최신순):
{notes}

위 메모들을 종합해 2~3문장으로 핵심 판단을 요약하세요.
메모에 없는 사실을 추가하지 마세요. 한국어로 작성하세요.
"""


def run() -> None:
    if not _NOTES_PATH.exists():
        print(f"[summarize_distillation] {_NOTES_PATH} 없음 — 스킵")
        return

    notes = json.loads(_NOTES_PATH.read_text(encoding="utf-8"))
    if not notes:
        print("[summarize_distillation] 메모 0건 — 스킵")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("::warning::ANTHROPIC_API_KEY not set — distillation summary skipped")
        return

    import anthropic

    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for n in notes:
        grouped[(n["axis"], n["category"])].append(n)

    client = anthropic.Anthropic(api_key=api_key)
    now_ts = datetime.now(timezone.utc).isoformat()
    out: dict = {}
    ok = fail = 0

    for (axis, category), group in grouped.items():
        group_sorted = sorted(group, key=lambda n: n["date"], reverse=True)[:20]
        notes_text = "\n".join(f"- [{n['date']}] {n['comment']}" for n in group_sorted)
        prompt = _PROMPT_TMPL.format(axis=axis, category=category, notes=notes_text)
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
                tools=[_TOOL],
                tool_choice={"type": "tool", "name": "category_summary"},
            )
            tool_block = next(b for b in resp.content if b.type == "tool_use")
            out[f"{axis}||{category}"] = {
                "summary": tool_block.input["summary"],
                "note_count": len(group),
                "generated_at": now_ts,
            }
            ok += 1
        except Exception as exc:
            print(f"::warning::summarize_distillation [{axis}/{category}] failed: {exc}")
            fail += 1

    _OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUT_PATH.write_text(
        json.dumps({"generated_at": now_ts, "summaries": out}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[summarize_distillation] ok={ok} fail={fail} → {_OUT_PATH}")


if __name__ == "__main__":
    run()
