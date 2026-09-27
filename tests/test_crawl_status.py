"""P0-3 빈 결과 게이트 — crawl_status 누적/경고 판정."""
from crawlers.common import crawl_status as cs


def _run(status, day, results):
    cs.record_crawlers(status, results, day)
    return cs.evaluate_alerts(status)


def test_streak_alerts_once_at_threshold():
    st = {"crawlers": {}, "sectors": {}}
    _run(st, "2026-09-01", {"a/x": (5, None)})
    assert st["crawlers"]["a/x"]["last_nonempty"] == "2026-09-01"
    for i, day in enumerate(["2026-09-02", "2026-09-03"]):
        new, active = _run(st, day, {"a/x": (0, None)})
        assert new == [] and active == []
    new, active = _run(st, "2026-09-04", {"a/x": (None, "timeout")})
    assert len(new) == 1 and "3일 연속" in new[0] and "2026-09-01" in new[0]
    new, active = _run(st, "2026-09-05", {"a/x": (0, None)})
    assert new == [] and len(active) == 1   # 이후는 active만
    new, active = _run(st, "2026-09-06", {"a/x": (3, None)})
    assert active == [] and st["crawlers"]["a/x"]["zero_streak"] == 0


def test_same_day_rerun_does_not_double_count():
    st = {"crawlers": {}, "sectors": {}}
    _run(st, "2026-09-01", {"a/x": (0, None)})
    _run(st, "2026-09-01", {"a/x": (0, None)})
    assert st["crawlers"]["a/x"]["zero_streak"] == 1


def test_removed_crawler_dropped():
    st = {"crawlers": {}, "sectors": {}}
    _run(st, "2026-09-01", {"a/x": (1, None), "a/y": (1, None)})
    _run(st, "2026-09-02", {"a/x": (1, None)})
    assert list(st["crawlers"]) == ["a/x"]


def test_sectors_zero_alerts_immediately():
    st = {"crawlers": {}, "sectors": {}}
    cs.record_sectors(st, 0, "2026-09-01")
    new, _ = cs.evaluate_alerts(st)
    assert len(new) == 1 and "섹터요약" in new[0]
    cs.record_sectors(st, 5, "2026-09-02")
    assert cs.evaluate_alerts(st) == ([], [])


def test_load_missing_file(tmp_path):
    assert cs.load_status(tmp_path / "none.json") == {"crawlers": {}, "sectors": {}}
