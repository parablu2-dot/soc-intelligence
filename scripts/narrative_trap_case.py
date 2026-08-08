#!/usr/bin/env python3
"""
서사 함정 파훼 프레임 - narrative-trap 케이스 관리

설계 원칙 (SoC Dashboard 기존 원칙 계승):
- runtime-token-zero: LLM 호출 없이 로컬에서 스키마/파일만 관리
- git-as-storage: DB 없음. data/narrative_trap/cases/ 에 JSON 파일로 축적 (baseline notes와 동일 패턴)
- Option B(수동) 우선 — narrative_gap/trap_type/judgment/unconfirmed/sources는 CLI로 추가한 뒤
  JSON 파일을 직접 열어 채워 넣는다. Option A(크롤러 diff 자동 추출)는 다음 단계.

다음 세션에서 정교화할 지점:
- [ ] 기존 크롤러 파이프라인과 연결할 diff-extraction 훅 (Option A)
"""

import json
import argparse
from dataclasses import dataclass, asdict, field
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "data" / "narrative_trap" / "cases"
OUT_PATH = ROOT / "data" / "refined" / "narrative_trap_cases.json"

# 표준 트랙별 소요기간 (년 단위, 2026-08-01 확정본)
STANDARD_TRACKS = {
    "greenfield_fab": {
        "label": "①원천기술~그린필드 팹",
        "stages": [
            ("PoC/개념검증", 0, 3),
            ("Pilot 구축", 3, 5.5),
            ("메인라인 건설", 5.5, 7.5),
            ("수율안정화", 7.5, 10),
        ],
        "total_range": (9.5, 12),
    },
    "logic_memory_new_product": {
        "label": "②로직/메모리 신제품",
        "stages": [("기획~양산", 0, 4.5)],
        "total_range": (3, 4.5),
    },
    "advanced_package": {
        "label": "③Advanced Package",
        "stages": [
            ("기획", 0, 0.5),
            ("설계·공정파일럿 통합", 0.5, 2.0),
        ],
        "total_range": (3, 4),
    },
    "node_vs_derivative": {
        "label": "④세대노드 vs 파생변형",
        "stages": [
            ("파생 변형(동일 세대)", 0, 1),
            ("신규 세대 노드", 0, 7),
        ],
        "total_range": (0.67, 7),
    },
}

GateStatus = str  # "pass" | "fail" | "미확인"


@dataclass
class NarrativeTrapCase:
    case_id: str
    title: str
    track: str  # STANDARD_TRACKS 키 중 하나
    announcement_date: str  # YYYY-MM-DD
    gate_design: GateStatus = "미확인"  # 설계 feasibility (성능)
    gate_yield: GateStatus = "미확인"   # 양산 feasibility (수율)
    standard_eta_range: str = ""        # 예: "2029~2031"
    narrative_gap: str = ""             # 압축 서사 요약 (1문장)
    trap_type: str = ""                 # ①분모은폐형 ②침묵독해형 ③기업문서vs시장서사 ④단일소스다중매체에코형(draft) 등 — 정의는 data/narrative_trap/trap_types.md 참고
    judgment: str = ""                  # 판단 (근거 포함)
    unconfirmed: list = field(default_factory=list)  # 미확인 항목 리스트
    sources: list = field(default_factory=list)

    def validate(self):
        if self.track not in STANDARD_TRACKS:
            raise ValueError(f"알 수 없는 트랙: {self.track} (선택지: {list(STANDARD_TRACKS)})")
        for g in (self.gate_design, self.gate_yield):
            if g not in ("pass", "fail", "미확인"):
                raise ValueError(f"gate 상태는 pass/fail/미확인 중 하나여야 함: {g}")


def save_case(case: NarrativeTrapCase):
    case.validate()
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    path = CASES_DIR / f"{case.case_id}.json"
    path.write_text(json.dumps(asdict(case), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장됨: {path}")


def load_all_cases() -> list[NarrativeTrapCase]:
    if not CASES_DIR.exists():
        return []
    cases = []
    for p in sorted(CASES_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        cases.append(NarrativeTrapCase(**data))
    return cases


def build_index():
    """narrative-trap 페이지용 정적 JSON 생성 — data/refined/narrative_trap_cases.json (baseline_notes.json과 동일 패턴)"""
    cases = load_all_cases()
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tracks": STANDARD_TRACKS,
        "cases": [asdict(c) for c in cases],
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"index 생성됨: {OUT_PATH} ({len(cases)}건)")


def cli():
    parser = argparse.ArgumentParser(description="narrative-trap 케이스 관리")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="새 케이스 추가")
    p_add.add_argument("--id", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--track", required=True, choices=list(STANDARD_TRACKS))
    p_add.add_argument("--announced", default=str(date.today()))
    p_add.add_argument("--gate-design", default="미확인")
    p_add.add_argument("--gate-yield", default="미확인")

    sub.add_parser("list", help="저장된 케이스 목록")
    sub.add_parser("build-index", help="data/refined/narrative_trap_cases.json 생성")

    args = parser.parse_args()

    if args.cmd == "add":
        case = NarrativeTrapCase(
            case_id=args.id,
            title=args.title,
            track=args.track,
            announcement_date=args.announced,
            gate_design=args.gate_design,
            gate_yield=args.gate_yield,
        )
        save_case(case)
    elif args.cmd == "list":
        for c in load_all_cases():
            print(f"[{c.case_id}] {c.title} | {c.track} | design={c.gate_design} yield={c.gate_yield}")
    elif args.cmd == "build-index":
        build_index()


if __name__ == "__main__":
    cli()
