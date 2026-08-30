"""tests/test_add_subscriber.py — add_subscriber.py 단위 테스트 (2026-08-30)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.add_subscriber as m


def _empty_subscribers_path() -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    json.dump([], tmp)
    tmp.close()
    return Path(tmp.name)


def test_add_subscriber_generates_unique_token_and_defaults():
    orig = m.SUBSCRIBERS_PATH
    m.SUBSCRIBERS_PATH = _empty_subscribers_path()
    try:
        result = m.add_subscriber("acme-corp", ["hpc_datacenter", "packaging"])
        assert "등록 완료" in result
        saved = json.loads(m.SUBSCRIBERS_PATH.read_text(encoding="utf-8"))
        assert len(saved) == 1
        rec = saved[0]
        assert rec["customer_id"] == "acme-corp"
        assert rec["axes"] == ["hpc_datacenter", "packaging"]
        assert rec["schedule"] == "weekday"
        assert rec["active"] is True
        assert len(rec["unsubscribe_token"]) > 16  # 실제 랜덤 토큰 생성됨
        assert "delivery_days" not in rec  # days 안 줬으면 필드 자체를 안 만듦(레거시 폴백 유지)
    finally:
        m.SUBSCRIBERS_PATH = orig


def test_placeholder_customer_id_literal_rejected():
    """과거 실수(placeholder 'customer_id'를 실제 값으로 씀) 재발 방지 확인."""
    orig = m.SUBSCRIBERS_PATH
    m.SUBSCRIBERS_PATH = _empty_subscribers_path()
    try:
        result = m.add_subscriber("customer_id", ["foundry"])
        assert "과거 실수 재발 방지" in result
        saved = json.loads(m.SUBSCRIBERS_PATH.read_text(encoding="utf-8"))
        assert saved == []  # 파일 무변경
    finally:
        m.SUBSCRIBERS_PATH = orig


def test_duplicate_customer_id_rejected():
    orig = m.SUBSCRIBERS_PATH
    path = _empty_subscribers_path()
    path.write_text(json.dumps([{"customer_id": "acme-corp", "axes": ["foundry"],
                                  "schedule": "weekday", "unsubscribe_token": "x", "active": True}]),
                     encoding="utf-8")
    m.SUBSCRIBERS_PATH = path
    try:
        result = m.add_subscriber("acme-corp", ["packaging"])
        assert "이미 존재" in result
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert len(saved) == 1  # 추가 안 됨
    finally:
        m.SUBSCRIBERS_PATH = orig


def test_invalid_axis_rejected():
    orig = m.SUBSCRIBERS_PATH
    m.SUBSCRIBERS_PATH = _empty_subscribers_path()
    try:
        result = m.add_subscriber("acme-corp", ["not_a_real_axis"])
        assert "알 수 없는 축" in result
    finally:
        m.SUBSCRIBERS_PATH = orig


def test_with_delivery_days():
    orig = m.SUBSCRIBERS_PATH
    m.SUBSCRIBERS_PATH = _empty_subscribers_path()
    try:
        m.add_subscriber("acme-corp", ["foundry"], days=["mon", "fri"])
        saved = json.loads(m.SUBSCRIBERS_PATH.read_text(encoding="utf-8"))
        assert saved[0]["delivery_days"] == ["mon", "fri"]
    finally:
        m.SUBSCRIBERS_PATH = orig
