"""
tests/test_subscriber_schema.py — subscriber_schema.py 단위 테스트

완료 기준(페르소나 Verifier 작업지시서):
  "subscribers 스키마 변경 후 기존 CPO 구독 레코드 정상 동작"
  → 강제 변환 없이 레거시 레코드가 폴백 경로로 정상 정규화되는지 검증.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.subscriber_schema import normalize_subscriber, AXES_ACTIVE, ROLE_TYPE_DOMAIN_SCOPE


def test_legacy_cpo_subscriber_falls_back_to_axes_as_primary():
    """실 라이브 레코드 형태(subscribers.json) — persona/domain_scope/role_type 전부 없음."""
    legacy = {
        "customer_id": "test-op",
        "axes": ["hpc_datacenter", "packaging", "cpo_optics"],
        "schedule": "weekday",
        "unsubscribe_token": "x",
        "active": True,
    }
    norm = normalize_subscriber(legacy)
    assert norm["persona"] is None
    assert norm["schedule_kind"] == "daily"  # weekday → daily 정규화
    assert norm["domain_scope"] == {
        "primary": ["hpc_datacenter", "packaging", "cpo_optics"],
        "adjacent": [],
    }


def test_role_type_derives_domain_scope():
    sub = {"customer_id": "c1", "persona": "leader", "role_type": "pmic_leader",
           "schedule": "weekly", "axes": []}
    norm = normalize_subscriber(sub)
    assert norm["persona"] == "leader"
    assert norm["schedule_kind"] == "weekly"
    assert norm["domain_scope"]["primary"] == ["pmic"]
    assert "dram" in ROLE_TYPE_DOMAIN_SCOPE["pmic_leader"]["adjacent"]  # 표 원문엔 있음
    assert "dram" not in norm["domain_scope"]["adjacent"]  # 아직 미가동 축이라 필터링됨


def test_explicit_domain_scope_overrides_role_type():
    sub = {"customer_id": "c2", "role_type": "nand_leader",  # 존재하지 않는 role_type
           "domain_scope": {"primary": ["hbm"], "adjacent": ["pmic"]}}
    norm = normalize_subscriber(sub)
    assert norm["domain_scope"] == {"primary": ["hbm"], "adjacent": ["pmic"]}


def test_invalid_persona_and_schedule_become_none():
    sub = {"customer_id": "c3", "persona": "ceo", "schedule": "hourly", "axes": ["foundry"]}
    norm = normalize_subscriber(sub)
    assert norm["persona"] is None
    assert norm["schedule_kind"] is None


def test_axes_active_excludes_deferred_dram_nand():
    assert "dram" not in AXES_ACTIVE
    assert "nand" not in AXES_ACTIVE
    assert "hbm" in AXES_ACTIVE and "pmic" in AXES_ACTIVE
