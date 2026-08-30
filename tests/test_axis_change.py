"""
tests/test_axis_change.py — process_axis_change.py 단위 테스트 (2026-08-30 기능 추가).

process_unsubscribe.py 테스트가 따로 없었지만(수동 스크립트라 CLI 레벨 검증만 해오던 관례),
이번엔 최소한의 회귀 방지용 테스트를 둔다 — 특히 잘못된 축 이름 거부 동작.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import scripts.process_axis_change as m


def _with_temp_subscribers(records: list[dict]):
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    json.dump(records, tmp, ensure_ascii=False)
    tmp.close()
    return Path(tmp.name)


def test_valid_token_updates_axes():
    orig = m.SUBSCRIBERS_PATH
    m.SUBSCRIBERS_PATH = _with_temp_subscribers([
        {"customer_id": "test-op", "axes": ["hpc_datacenter"], "schedule": "weekday",
         "unsubscribe_token": "TOK1", "active": True},
    ])
    try:
        result = m.process_token("TOK1", ["foundry", "pmic"])
        assert "축 변경 완료" in result
        saved = json.loads(m.SUBSCRIBERS_PATH.read_text(encoding="utf-8"))
        assert saved[0]["axes"] == ["foundry", "pmic"]
        assert "axes_changed_at" in saved[0]
    finally:
        m.SUBSCRIBERS_PATH = orig


def test_unknown_axis_rejected_without_mutating_file():
    orig = m.SUBSCRIBERS_PATH
    path = _with_temp_subscribers([
        {"customer_id": "test-op", "axes": ["hpc_datacenter"], "schedule": "weekday",
         "unsubscribe_token": "TOK1", "active": True},
    ])
    m.SUBSCRIBERS_PATH = path
    try:
        result = m.process_token("TOK1", ["not_a_real_axis"])
        assert "알 수 없는 축" in result
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert saved[0]["axes"] == ["hpc_datacenter"]  # 변경 안 됨
    finally:
        m.SUBSCRIBERS_PATH = orig


def test_wrong_token_not_found():
    orig = m.SUBSCRIBERS_PATH
    m.SUBSCRIBERS_PATH = _with_temp_subscribers([
        {"customer_id": "test-op", "axes": ["hpc_datacenter"], "schedule": "weekday",
         "unsubscribe_token": "TOK1", "active": True},
    ])
    try:
        result = m.process_token("WRONG", ["foundry"])
        assert "찾지 못했습니다" in result
    finally:
        m.SUBSCRIBERS_PATH = orig


def test_empty_axes_rejected():
    orig = m.SUBSCRIBERS_PATH
    m.SUBSCRIBERS_PATH = _with_temp_subscribers([
        {"customer_id": "test-op", "axes": ["hpc_datacenter"], "schedule": "weekday",
         "unsubscribe_token": "TOK1", "active": True},
    ])
    try:
        result = m.process_token("TOK1", [])
        assert "최소 1개 이상" in result
    finally:
        m.SUBSCRIBERS_PATH = orig
