"""
공통 출력 스키마.
모든 크롤러의 refine() 결과는 이 dataclass 리스트여야 한다.
site/의 프론트엔드가 이 필드에 직접 의존하므로 임의 변경 금지.

Phase 0.5 추가: BaselineFact, ProductLifecycleEvent, DistillationNote
  — RefinedSignal에 optional 필드 3개 추가 (기존 JSON은 필드 미포함 → site에서 undefined로 처리)
"""
from dataclasses import dataclass, asdict, field
from datetime import date
from typing import Optional


@dataclass
class RefinedSignal:
    axis: str            # "mobile_ap" | "hpc_datacenter" | "custom_soc" | "foundry" | "packaging"
    company: str          # "apple", "nvidia", "broadcom" 등 소문자 슬러그
    category: str         # "news" | "price" | "hiring" | "process" | "packaging"
    headline: str
    url: str
    published_date: date
    source: str           # 출처명 (예: "Reuters", "DigiTimes")
    tags: Optional[list[str]] = None   # 예: ["2nm", "CoWoS", "UCIe"]
    summary: Optional[str] = None      # 2~3문장 요약 (원문 재현 금지, 반드시 paraphrase)
    # ── Phase 0.5: Baseline+Diff 필드 (nullable — 기존 크롤러 변경 불필요) ──
    diff_type: Optional[str] = None    # "confirm" | "update_candidate" | "noise" | None
    baseline_ref: Optional[str] = None # 연결된 BaselineFact.id (nullable)
    verified: Optional[bool] = None    # HITL 검증 완료 여부
    # ── Phase 4: 소스 신뢰등급 (nullable — 기존 크롤러 변경 불필요) ──
    source_tier: Optional[str] = None  # "primary" | "aggregator" | None (Google News 등 aggregator 표시)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["published_date"] = self.published_date.isoformat()
        # None 필드는 직렬화에서 제외 (기존 JSON 호환)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class FoundryCapacityRecord:
    """파운드리·패키징 공정별 캐파/가격/수율 정형 데이터.
    RefinedSignal과 별도로 data/refined/foundry/capacity_records.json에 저장.
    Phase 3 backfill_capacity.py로 과거 3년치 채움.
    """
    axis: str                           # "foundry" | "packaging"
    company: str                        # "tsmc", "ase" 등 소문자 슬러그
    node: str                           # "3nm", "CoWoS-L" 등 공정 또는 패키징 타입
    month: str                          # "YYYY-MM"
    wafer_capacity: Optional[int] = None     # 월별 투입 가능량 (wafer starts/month, 단위: wspm)
    price_per_wafer: Optional[float] = None  # Fully Processed 기준 USD
    yield_rate: Optional[float] = None       # 0.0~1.0
    is_forecast: bool = False
    source: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None or k in ("is_forecast",)}


# ── Phase 0.5: Baseline+Diff 전략 ──────────────────────────────────────────

@dataclass
class BaselineFact:
    """고신뢰 검증 노드 — 3계층 Distillation의 1계층.
    저빈도로 바뀌는 사실(전략·시장점유율·투자결정)을 1회 큐레이션 후 diff로만 갱신.
    저장: data/baseline/{axis}/{company}.json
    """
    id: str                             # "{axis}_{company}_{yyyymmdd}_{seq}" 형태
    axis: str
    company: str
    category: str                       # "strategy" | "ecosystem" | "capa"
    fact: str                           # paraphrase 요약 (원문 복사 금지)
    source_type: str                    # "quarterly" | "annual" | "investor_day" | "analyst_report"
    as_of: str                          # "YYYY-MM-DD"
    next_review_due: Optional[str] = None  # "YYYY-MM" 분기/연 단위
    source_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class ProductLifecycleEvent:
    """SoC 제품 또는 공정 트랙의 라이프사이클 이벤트.
    CHANGES-v3 Phase 0.5 정의:
      - SoC 트랙: planning(dark) → design_win → performance → mass_production
      - Foundry 트랙: capex_investment → roadmap_disclosed → order_win → yield_performance
    저장: data/lifecycle/{axis}/{company}.json
    """
    axis: str
    track: str                          # "soc_product" | "foundry_process"
    company: str
    product_or_node: str                # 예: "A18 Pro", "N3E", "CoWoS-L"
    event_type: str                     # see track tables above
    visibility: str                     # "dark" | "partial" | "reliable"
    event_date: str                     # "YYYY-MM" or "YYYY-QQ" (예: "2024-Q3")
    source_type: str                    # "expert_analysis" | "youtuber_review" | "press_release" | "analyst_report"
    detail: Optional[str] = None
    linked_signal_url: Optional[str] = None  # 연결된 RefinedSignal URL

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class DistillationNote:
    """1차 증류 워크플로 — 그룹(축/카테고리) 단위 코멘트.
    append-only: 판단이 바뀐 이력도 자산이므로 수정 금지, 누적만 허용.
    저장: localStorage('distillation_notes') — 브라우저 측 영속.
    """
    id: str                             # UUID or timestamp-based
    date: str                           # "YYYY-MM-DD"
    axis: str
    category: str                       # "news" | "process" | "hiring" | event_type
    linked_signal_urls: list[str]       # 이 그룹에 속한 RefinedSignal URL 목록
    comment: str                        # 사람이 읽고 남긴 판단 (자유서술)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TechSignal:
    """기술 소스(논문·특허) — Phase 5, item 3. 뉴스 파이프라인(RefinedSignal)과 분리된
    별도 source class. axis/company 없음 — 경쟁사 축이 아니라 기술 자체가 단위.
    저volocity·고신호라 dedup_gate/merge_refine을 거치지 않고 URL 기준 누적만 한다
    (켜뮤 증류 후보 stratum). 저장: data/refined/tech/{source_class}.json
    """
    lens: str              # "tech" 고정 — 뉴스 lens와 구분
    source_class: str      # "paper" | "patent" | "journal"
    category: str          # arXiv: "cs.AR" 등 원본 분류 코드
    title: str
    url: str
    published_date: str    # "YYYY-MM-DD"
    source: str             # "arXiv" 등
    summary: Optional[str] = None
    authors: Optional[list[str]] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class PatentSignal:
    """기술 소스 — 특허 (Phase 5, item 3 후속). TechSignal(논문)과도 별개 클래스 —
    자연 유니크키(publication_number)라 URL 기준 누적과 달리 그 자체로 idempotent.
    크롤러가 아니라 GHA cron에서 BigQuery(patents-public-data.patents.publications) 직접 조회로 채움.
    저장: data/refined/tech/patents.json (dedup_gate ingestion 제외 대상 — arxiv.py와 동일 취급)
    """
    # ── 자연 유니크키 ──
    publication_number: str            # e.g. "US-11234567-B2"

    # ── 확정 필드 (BigQuery patents.publications) ──
    assignee_harmonized: str
    cpc: list[str]                     # e.g. ["H01L23/48", "H01L21/768"]
    filing_date: date
    publication_date: date
    title: str
    abstract: str

    # ── 파이프라인 메타 ──
    axis: str                          # mobile_ap | hpc_datacenter | custom_soc | foundry | packaging | component_intelligence
    source_tier: str = "primary"       # news=aggregator와 구분
    url: Optional[str] = None          # patents.google.com/patent/{publication_number}

    # ── distill lens="patent" 산출 (초기 None, 리뷰층에서 채움) ──
    bom_implication: Optional[str] = None
    derivation_type: Optional[str] = None

    # tentative: google_patents_research.publications 스키마 실측 후 확정
    top_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["filing_date"] = self.filing_date.isoformat()
        d["publication_date"] = self.publication_date.isoformat()
        return {k: v for k, v in d.items() if v is not None and v != []}


@dataclass
class BomImplication:
    """component-intelligence axis — downstream 디바이스/칩셋 수요를 부품·기판 수요로 파생.
    facts/inferences 분리 원칙에서 inference 하위 (RefinedSignal의 사실 위에 얹는 정성 판단).
    static 매핑 — LLM은 distill 시점 규칙 적용만, runtime-token-zero 유지.
    저장: data/baseline/bom_implications.json
    """
    component_group: str    # "MLCC" | "substrate" | "module" | "inductor" | "silicon_cap" | "glass_substrate"
    device_axis: str        # "server" | "mobile" | "pc"
    direction: str           # "up" | "down" | "neutral"
    basis_fact_id: str       # facts[] 참조 (BaselineFact.id 또는 서술적 slug — 실 BaselineFact 부재 시)
    strength_hint: str       # "strong" | "moderate" | "weak" — 정성. 유닛 예측 아님
    derivation_type: str     # "content" | "leading" | "near_fact" | "transition"

    def to_dict(self) -> dict:
        return asdict(self)
