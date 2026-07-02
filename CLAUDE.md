# SoC Intelligence Dashboard

## 프로젝트 개요
SK hynix China Memory Benchmark Dashboard를 벤치마킹해 만드는 **SoC(System on Chip) 경쟁 인텔리전스 대시보드**.
3축(Mobile AP / HPC·Datacenter / Custom SoC)의 신호를 정적 크롤링→빌드 파이프라인으로 수집·시각화한다.
**런타임 토큰 0**이 핵심 원칙: 크롤러는 결정론적 스크립트로 동작하며, LLM(Claude Code)은 스캐폴딩·변경분 처리에만 개입한다.

## 도메인 축 (5-Axis, v2)
| 축 | 대상 | 폴더 |
|---|---|---|
| Mobile AP | Apple, Qualcomm, MediaTek, Unisoc, Exynos | `crawlers/mobile_ap/` |
| HPC·Datacenter | NVIDIA, AMD, Intel, SK hynix, Tesla | `crawlers/hpc_datacenter/` |
| Custom SoC | Broadcom, Marvell, 하이퍼스케일러 인하우스(Trainium/TPU/Maia) | `crawlers/custom_soc/` |
| Foundry(공정) | TSMC, Samsung Foundry, Intel Foundry, GlobalFoundries, SMIC | `crawlers/foundry/` |
| Packaging(패키징) | ASE, Amkor, JCET | `crawlers/packaging/` |

공통 신호축: 공정 노드(2nm 이하) · 첨단 패키징(CoWoS/InFO/UCIe) · 파운드리 캐파 배분.
(v1의 "3축 + 공정/패키징 태그" 구조에서 5축 병렬 구조로 승격 — 상세는 CHANGES-v2.md 참고)

## 저장소 구조
```
soc-intelligence/
├── crawlers/
│   ├── common/          # base_crawler.py, schema.py — 공통 인터페이스
│   ├── mobile_ap/
│   ├── hpc_datacenter/
│   ├── custom_soc/
│   ├── foundry/         # v2 추가: tsmc, samsung_foundry, intel_foundry, globalfoundries, smic
│   └── packaging/       # v2 추가: ase, amkor, jcet
├── data/
│   ├── raw/              # 크롤러 원본 출력
│   └── refined/          # 정규화·태깅된 JSON (사이트가 직접 fetch)
├── site/                 # 정적 HTML/JS (17개 모듈)
├── .github/workflows/     # crawl-and-build.yml
└── CLAUDE.md              # 이 파일
```

## 데이터 파이프라인
```
Crawl (crawlers/*, LLM 미개입) → Refine (정규화·dedupe·축 태깅) → Build (site/가 refined JSON만 읽음)
```
GitHub Actions cron으로 스케줄 실행. 브라우저 런타임에서 외부 API 호출 없음.

## 13개 모듈 (v2 Phase 1 통폐합 완료)
오늘의 요약 · 일일 리뷰 큐(5축 필터) · 크롤링 관제 · 파운드리 캐파 · 기사(영어/중문/한국어) ·
SoC 생태계·다이나믹스 · 인재·채용 레이더 · 숫자 대시보드 · 벤치마크 성능(워크벤치+벤치마킹 통합) ·
공정·패키징 매트릭스 · SoC 카테고리(5축) · 업체별 주요 전략 · 정보 획득 채널
(삭제: 심층 벤치마킹, 경쟁 다이나믹스, 벤치마킹 모델, 대응 대시보드)

## 작업 규칙 (Claude Code 세션용)
1. **크롤러 실행/수정은 스크립트 레벨에서** — 개별 크롤러 실행에 LLM 호출 넣지 않는다.
2. **신규 소스 추가 시**: `crawlers/{axis}/{company}.py`에 `BaseCrawler` 상속 클래스만 추가, `config.yaml`에 등록.
3. **세션 범위는 diff 단위로 제한** — 전체 구조 재설명 없이 변경 파일만 언급.
4. **출력 스키마 고정**: `schema.py`의 `RefinedSignal` 필드를 임의로 바꾸지 않는다 (site/가 이 스키마에 의존).
5. **소스 도메인 제외 없음** — 원본은 .kr 뉴스를 제외했지만, 3계층 distillation의 검증 노드가 출처 신뢰도를 개별 판단하므로 도메인 단위 사전 필터링은 하지 않는다.

## 3계층 Distillation 연동 (Phase 0.5 스키마 완료)
- **검증 노드** = `RefinedSignal` + `diff_type`("confirm"|"update_candidate"|"noise") — 스키마 구현
- **기준 사실** = `BaselineFact` — 저빈도 고신뢰 사실, `data/baseline/{axis}/{company}.json` 저장
- **라이프사이클** = `ProductLifecycleEvent` — SoC/Foundry 트랙 2개, 단계별 visibility 분류
- **1차 증류** = `DistillationNote` — 일일 리뷰 큐 코멘트, localStorage append-only 저장
- **추론 노드** = 경쟁 다이나믹스·업체별 전략 등 축 간 교차 해석 모듈 (향후 단계)

## 스키마 작업 규칙 (추가)
6. **RefinedSignal 추가 허용 필드**: Phase 0.5에서 `diff_type`, `baseline_ref`, `verified` optional 필드 추가 완료. 이후 필드 추가 시 반드시 `Optional[str] = None` (nullable·기본값)으로, `to_dict()`에서 None 제외 직렬화 유지.
7. **capacity_records.json 갱신**: `scripts/backfill_capacity.py` 실행. 신규 투자 발표 뉴스는 TrendForce 크롤러 diff로 추가 (수동 편집 금지).

## 현재 진행 상태
- [x] 3축 구조 설계 → 5축으로 승격 (v2)
- [x] CLAUDE.md 초안
- [x] crawlers/ 구현 완료 (22개: 기존 19 + trendforce·etnews·hiring)
- [x] site/ 정적 프론트엔드
- [x] GitHub Actions 워크플로 (crawl-and-build.yml)
- [x] v2 Phase 0 — 5축 스키마/폴더 확장, FoundryCapacityRecord 신설
- [x] v2 Phase 1 — 17모듈 → 13모듈 통폐합
- [x] v2 Phase 2 — UI/인터랙션 (5축 인터랙티브 그래프, 오늘의 요약 드릴다운)
- [x] v2 Phase 3 — 데이터 갭 보완 (캐파 실소스, 한국어 소스, 채용 레이더)
- [x] v2 Phase 3 정교화 — SK하이닉스·Micron·Tesla 채용 피드, FoundryCapacityRecord 51건 백필, Phase 0.5 스키마(BaselineFact/ProductLifecycleEvent/DistillationNote/diff_type), 일일 리뷰 큐 1차 증류 코멘트 UI
- [ ] BaselineFact 실데이터 큐레이션 — `data/baseline/` 수동 입력 또는 별도 백필 스크립트
- [ ] ProductLifecycleEvent 백필 — 회사당 1.5~6개 이벤트, 3년치 수동 큐레이션 예정
