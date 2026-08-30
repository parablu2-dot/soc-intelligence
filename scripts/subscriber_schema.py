"""
subscriber_schema.py — 페르소나 Verifier 구독자 스키마 확장 (2026-08-30 기획 문서 §1·§2·§7).

기존 subscribers.json 레코드(customer_id/axes/schedule="weekday"/unsubscribe_token/active/created_at,
2026-08-11 CPO 구독시스템)를 **강제 변환하지 않는다** — 실 고객 2건이 이미 이 형태로 라이브 중이고
send_subscriber_mail.py가 이 필드들을 직접 읽는다. 대신 이 모듈이 신규(persona/role_type/domain_scope/
schedule 확장값) 필드를 옵션으로 얹고, 레코드에 없으면 기존 동작과 동일하게 폴백하는 정규화 계층
역할을 한다 (CLAUDE.md 규칙 6 — "Optional, nullable, 기본값 유지"와 동일 원칙을 스키마 밖 JSON에 적용).

레코드에 아래 필드가 추가되면 이 모듈이 인식한다 (전부 optional):
  - persona:    "exec" | "leader" | "staff"          (없으면 None — 주간/월간 발송 대상에서 제외)
  - role_type:  ROLE_TYPE_DOMAIN_SCOPE의 키 중 하나    (있으면 domain_scope를 여기서 자동 도출)
  - domain_scope: {"primary": [...], "adjacent": [...]} (role_type보다 우선 — 직접 지정 시 그대로 사용)
  - schedule:   기존 "weekday" 리터럴 그대로 두거나, 신규 "daily"|"weekly"|"monthly" 사용 가능
"""
from __future__ import annotations

# ── 10축 확정 (기획 §1) — DRAM/NAND는 이번 구현 라운드에서 보류(크롤러·distillation 미착수).
# 여기 순서/존재 여부만으로 축이 "실제로 도네이터를 갖는지"가 결정되지 않는다 — 실제 수집 축은
# crawlers/config.yaml 등록 여부로 별도 판단한다. AXES_10에는 최종 10개를 전부 적어 두고
# AXES_ACTIVE만 지금 실제로 파이프라인이 도는 축으로 구분해, DRAM/NAND 추가 시 이 파일 값 변경
# 없이 role_type 매핑표가 자동으로 살아나게 한다.
AXES_10 = [
    "mobile_ap", "hpc_datacenter", "custom_soc", "foundry", "packaging",
    "cpo_optics", "dram", "nand", "hbm", "pmic",
]
AXES_ACTIVE = [
    "mobile_ap", "hpc_datacenter", "custom_soc", "foundry", "packaging",
    "cpo_optics", "hbm", "pmic",
]  # DRAM/NAND 제외 — 나중에 추가 시 여기에만 반영

PERSONAS = ("exec", "leader", "staff")
SCHEDULES = ("daily", "weekly", "monthly")
_LEGACY_SCHEDULE_MAP = {"weekday": "daily"}  # 기존 CPO 구독 레코드 호환

# ── 역할 유형 → domain_scope 매핑 (기획 §2 표 그대로) ───────────────────────────
# NAND는 구조적으로 고립 축(표에서 드러난 발견, §2 후반부) — adjacent가 얇은 게 정상.
ROLE_TYPE_DOMAIN_SCOPE: dict[str, dict[str, list[str]]] = {
    "mobile_ap_leader": {
        "primary": ["mobile_ap"],
        "adjacent": ["foundry", "packaging", "dram", "pmic"],
    },
    "custom_soc_leader": {
        "primary": ["custom_soc", "hpc_datacenter"],
        "adjacent": ["packaging", "hbm", "cpo_optics", "pmic"],
    },
    "foundry_leader": {
        "primary": ["foundry", "packaging"],
        "adjacent": ["mobile_ap", "custom_soc", "hpc_datacenter"],
    },
    "memory_leader_dram_hbm": {
        "primary": ["dram", "hbm"],
        "adjacent": ["hpc_datacenter", "custom_soc", "packaging", "pmic"],
    },
    "memory_leader_nand": {
        "primary": ["nand"],
        "adjacent": ["hpc_datacenter", "dram"],
    },
    "packaging_cpo_leader": {
        "primary": ["packaging", "cpo_optics"],
        "adjacent": ["hbm", "hpc_datacenter", "foundry"],
    },
    "pmic_leader": {
        "primary": ["pmic"],
        "adjacent": ["mobile_ap", "hpc_datacenter", "dram", "foundry"],
    },
}


def _filter_active(axes: list[str]) -> list[str]:
    """DRAM/NAND 등 아직 파이프라인이 없는 축은 콘텐츠 생성 단계에서 조용히 제거.
    role_type 표 자체는 건드리지 않아 나중에 AXES_ACTIVE에 추가되는 순간 자동 복원됨."""
    return [a for a in axes if a in AXES_ACTIVE]


def normalize_subscriber(sub: dict) -> dict:
    """구독자 레코드 1건을 읽어 persona/domain_scope/schedule_kind를 결정론적으로 채운 사본을 반환.
    원본 dict는 수정하지 않는다(append-only 원칙, 실제 subscribers.json에도 아무것도 안 씀).

    반환 필드:
      persona        — 명시 값 그대로, 없으면 None
      schedule_kind  — "daily"|"weekly"|"monthly" 정규화값 (레거시 "weekday"→"daily"), 매칭 실패 시 None
      domain_scope   — {"primary": [...], "adjacent": [...]} (아래 우선순위로 결정)
                        1) sub["domain_scope"] 직접 지정
                        2) sub["role_type"]으로 ROLE_TYPE_DOMAIN_SCOPE 조회
                        3) 레거시 폴백: sub["axes"] 전체를 primary로, adjacent는 빈 리스트
                           (기존 CPO 구독자 2건이 여기로 떨어짐 — 동작 변화 없음)
    """
    persona = sub.get("persona")
    if persona not in PERSONAS:
        persona = None

    raw_schedule = sub.get("schedule")
    schedule_kind = _LEGACY_SCHEDULE_MAP.get(raw_schedule, raw_schedule)
    if schedule_kind not in SCHEDULES:
        schedule_kind = None

    domain_scope = sub.get("domain_scope")
    if not domain_scope:
        role_type = sub.get("role_type")
        if role_type in ROLE_TYPE_DOMAIN_SCOPE:
            domain_scope = ROLE_TYPE_DOMAIN_SCOPE[role_type]
        else:
            domain_scope = {"primary": list(sub.get("axes") or []), "adjacent": []}

    return {
        "persona": persona,
        "schedule_kind": schedule_kind,
        "domain_scope": {
            "primary": _filter_active(domain_scope.get("primary") or []),
            "adjacent": _filter_active(domain_scope.get("adjacent") or []),
        },
    }
