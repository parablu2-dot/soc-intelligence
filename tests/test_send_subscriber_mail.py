"""
tests/test_send_subscriber_mail.py — send_subscriber_mail.py 단위 테스트 (2026-08-30 추가 기능).

커버 대상:
  - 메일이 한국어만 렌더하고 English 섹션을 더 이상 포함하지 않는지
  - 구독자별 delivery_days 게이트 (레거시 폴백 포함)
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.send_subscriber_mail as m


def test_axis_block_html_is_korean_only():
    content = {
        "ko": {"executive_summary": "한글 요약", "key_facts": [], "implications": [], "counterpoint": ""},
        "en": {"executive_summary": "English summary", "key_facts": [], "implications": [], "counterpoint": ""},
    }
    html = m._axis_block_html("AI 서버", content, [])
    assert "한글 요약" in html
    assert "English summary" not in html
    assert ">English<" not in html


def _monkeypatch_kst(monkeypatch, iso: str):
    dt = datetime.fromisoformat(iso)
    monkeypatch.setattr(m, "_kst_now", lambda: dt)


def test_is_delivery_day_legacy_fallback_matches_weekday(monkeypatch):
    # 2026-08-31은 월요일 — delivery_days 없는 레거시 구독자는 평일 전체(월~금) 규칙 그대로
    _monkeypatch_kst(monkeypatch, "2026-08-31T05:00:00")
    sub = {"customer_id": "legacy", "axes": ["foundry"]}
    assert m._is_delivery_day(sub) is True


def test_is_delivery_day_legacy_fallback_excludes_weekend(monkeypatch):
    # 2026-08-30은 일요일
    _monkeypatch_kst(monkeypatch, "2026-08-30T05:00:00")
    sub = {"customer_id": "legacy", "axes": ["foundry"]}
    assert m._is_delivery_day(sub) is False


def test_is_delivery_day_respects_explicit_days_even_on_weekend(monkeypatch):
    # 2026-08-30은 일요일이지만 구독자가 sun을 직접 지정했으면 받아야 함
    _monkeypatch_kst(monkeypatch, "2026-08-30T05:00:00")
    sub = {"customer_id": "weekender", "axes": ["foundry"], "delivery_days": ["sun"]}
    assert m._is_delivery_day(sub) is True


def test_is_delivery_day_explicit_days_excludes_unlisted_weekday(monkeypatch):
    # 2026-08-31은 월요일이지만 구독자가 mon을 뺐으면 스킵
    _monkeypatch_kst(monkeypatch, "2026-08-31T05:00:00")
    sub = {"customer_id": "tuesday-only", "axes": ["foundry"], "delivery_days": ["tue"]}
    assert m._is_delivery_day(sub) is False
