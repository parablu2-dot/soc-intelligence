"""LLM 계정 수준 오류를 워크플로 빨간불로 드러내기 위한 공유 헬퍼.

2026-09-22~26 API 크레딧 소진 때 각 스크립트가 ::warning::만 찍고 워크플로는
성공(초록)으로 끝나, 섹터 요약·주간 리포트가 빠진 채 메일이 나가는데도 아무도 몰랐음.
개별 호출의 일시 오류는 기존대로 fail-soft로 두고, 모든 호출이 실패할 계정 수준
오류(크레딧 소진·인증·잘못된 모델 ID)만 .llm-errors.log에 남긴다. 워크플로 마지막
"Fail on LLM errors" 스텝이 이 파일을 보고 exit 1 한다.
"""

from __future__ import annotations

import re
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parents[1] / ".llm-errors.log"

_ACCOUNT_LEVEL_RE = re.compile(
    r"credit balance|authentication_error|permission_error|not_found_error", re.IGNORECASE
)


def record_llm_error(tag: str, exc: BaseException) -> None:
    msg = str(exc)
    if not _ACCOUNT_LEVEL_RE.search(msg):
        return
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{tag}] {type(exc).__name__}: {msg[:300]}\n")
