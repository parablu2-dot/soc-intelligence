"""
check_empty_results.py — P0-3 빈 결과 게이트 판정 (crawl-and-build, summarize_sectors 다음).

- sector_summaries.json의 섹터 수를 crawl_status.json에 기록
- 크롤러(run_all.py가 기록)·섹터요약 연속 0건 판정 → ::warning::
- 임계치에 오늘 처음 도달한 경고는 .crawl-alerts.log에 남김 → 워크플로가 deploy 이후 crawl-health job을 빨간불로

LLM 미개입. 실패해도 파이프라인은 계속 가야 하므로 항상 exit 0.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawlers.common import crawl_status  # noqa: E402

SECTOR_PATH = ROOT / "data" / "refined" / "sector_summaries.json"
ALERT_LOG = ROOT / ".crawl-alerts.log"


def run() -> None:
    status = crawl_status.load_status()
    try:
        sectors = json.loads(SECTOR_PATH.read_text(encoding="utf-8")).get("sectors") or {}
        count = sum(1 for v in sectors.values() if v)
    except (FileNotFoundError, json.JSONDecodeError):
        count = 0
    crawl_status.record_sectors(status, count, crawl_status.today_kst())

    new, active = crawl_status.evaluate_alerts(status)
    crawl_status.save_status(status)

    for msg in active:
        print(f"::warning::빈 결과 게이트 — {msg}")
    if new:
        ALERT_LOG.write_text("\n".join(new) + "\n", encoding="utf-8")
    print(f"[check_empty_results] sectors={count} active={len(active)} new={len(new)}")


if __name__ == "__main__":
    run()
