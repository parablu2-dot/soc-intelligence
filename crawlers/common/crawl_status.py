"""
P0-3 빈 결과 게이트 — 크롤러별/섹터요약 수집 건수를 data/refined/crawl_status.json에 누적.

크롤러는 매 실행 피드 전체를 다시 파싱하므로 정상이면 0건이 나올 일이 거의 없다.
0건(또는 예외)이 ZERO_STREAK_ALERT일 연속되면 파손으로 보고 경고한다.
경고는 "임계치에 처음 도달한 날"만 new_alerts로 올려 워크플로를 빨간불로 만들고(llm-health와 같은 방식),
그 이후 계속되는 0건은 active_alerts에만 남긴다(매일 빨간불이면 다른 장애가 묻힘).

LLM 미개입, 결정론적.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATUS_PATH = Path(__file__).resolve().parents[2] / "data" / "refined" / "crawl_status.json"

ZERO_STREAK_ALERT = 3      # 업체 크롤러: N일 연속 0건/실패면 경고
SECTOR_STREAK_ALERT = 1    # 섹터 요약: 하루라도 0개면 경고 (구독자 메일이 비어서 나감)

_KST = timezone(timedelta(hours=9))


def today_kst() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


def load_status(path: Path = STATUS_PATH) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"crawlers": {}, "sectors": {}}


def save_status(status: dict, path: Path = STATUS_PATH) -> None:
    status["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_entry(entry: dict, count: int | None, error: str | None, today: str) -> dict:
    # 같은 날 재실행(workflow_dispatch)은 streak를 한 번만 올림
    same_day = entry.get("last_run") == today
    prev_streak = entry.get("zero_streak", 0)
    if same_day:
        prev_streak = entry.get("_streak_before_today", 0)
    empty = error is not None or not count
    entry["_streak_before_today"] = prev_streak
    entry["zero_streak"] = prev_streak + 1 if empty else 0
    entry["last_run"] = today
    entry["last_count"] = count
    entry["error"] = error
    if not empty:
        entry["last_nonempty"] = today
    entry.setdefault("last_nonempty", None)
    return entry


def record_crawlers(status: dict, results: dict[str, tuple[int | None, str | None]], today: str) -> dict:
    """results: {"axis/company": (count, error)}. 이번에 실행 안 된(=config에서 빠진) 항목은 제거."""
    crawlers = status.setdefault("crawlers", {})
    for key in list(crawlers):
        if key not in results:
            del crawlers[key]
    for key, (count, error) in results.items():
        crawlers[key] = _update_entry(crawlers.get(key, {}), count, error, today)
    return status


def record_sectors(status: dict, count: int, today: str) -> dict:
    status["sectors"] = _update_entry(status.get("sectors") or {}, count, None, today)
    return status


def evaluate_alerts(status: dict) -> tuple[list[str], list[str]]:
    """(new_alerts, active_alerts). new는 임계치에 오늘 처음 도달한 것만."""
    new, active = [], []

    def check(name: str, entry: dict, threshold: int) -> None:
        streak = entry.get("zero_streak", 0)
        if streak < threshold:
            return
        why = f"오류: {entry['error']}" if entry.get("error") else "0건"
        msg = f"{name} {streak}일 연속 {why} (마지막 수집일 {entry.get('last_nonempty') or '없음'})"
        active.append(msg)
        if streak == threshold:
            new.append(msg)

    for key, entry in sorted(status.get("crawlers", {}).items()):
        check(key, entry, ZERO_STREAK_ALERT)
    if status.get("sectors"):
        check("섹터요약(sectors)", status["sectors"], SECTOR_STREAK_ALERT)
    status["alerts"] = active
    return new, active
