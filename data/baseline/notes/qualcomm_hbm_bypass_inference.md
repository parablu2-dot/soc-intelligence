---
type: DistillationNote
status: "#stub"
date: 2026-07-06
source: 커피 토론 (Qualcomm HBM-less 데이터센터 AI 칩)
tags: [접점전쟁, 수요의소유, 추론, 메모리, SoC, Qualcomm]
---

# Qualcomm의 HBM 우회 전략 — 추론 메모리 아키텍처

## 핵심 명제 (천의 정리)

Qualcomm은 Mobile Computing 역량을 바탕으로 **Prefill의 Compute-bound 구간은 SRAM 등을 이용해 대응**하고, Memory-IO-bound 구간은 HBM을 빼고 LPDDR 등을 최대화하는 아키텍처를 기반으로, HBM을 제외한 Platform으로 엮어서 파는 방법을 제안하였다. HBM을 우회해서 가기는 어렵기 때문에, 시장 진입을 위해 자기가 가진 역량을 최대한 발휘하여 진입하려고 한다. 다만 **SRAM / LPDDR / (HBM)을 연결하는 Architecture가 핵심**이므로 Qualcomm이 이를 개발하고 있을 것으로 추측한다.

## 인과 사슬 (오늘의 벼리)

> **연산 강도(Arithmetic Intensity) → bound 종류 → 필요한 메모리 특성**

- **Prefill** = GEMM(행렬×행렬), 가중치 1회 읽어 N토큰 재사용 → 연산 강도 高 → **compute-bound** → 크기보다 "재사용 활성값을 초고속·저전력으로 굴리는" 스크래치패드가 필요 → **SRAM** (수십 MB, TB/s급, 낮은 pJ/bit)
- **Decode** = GEMV(행렬×벡터), 매 토큰마다 가중치 전체 + KV캐시(수십 GB) 읽음 → 연산 강도 ≈ 1 → **memory-bound** → 반드시 큰 오프칩 DRAM 필요 → HBM(빠르나 비쌈·CoWoS 종속) vs **LPDDR**(느리나 GB당 싸고 저전력)
- **Batch 확대** → 가중치 읽기 1회를 여러 시퀀스가 공유 → Decode의 연산 강도 상승 → LPDDR의 낮은 대역폭 약점을 상쇄

## 파는 Metric

지연(single-user latency)이 아니라 **tokens/sec/$ (TCO)**와 **tokens/sec/Watt**. 즉 "한 사용자에게 빠르냐"가 아니라 "요청 묶음 전체를 얼마나 싸게 처리하냐"로 경기장을 바꾸는 전략.

## 프레임 연결

- **접점 전쟁** : HBM이라는 지배적 접점(+엔비디아·메모리 3사·TSMC 동맹)을 우회하는 새 접점 개설 시도
- **수요의 소유** : 하이퍼스케일러가 "제2 공급선"을 능동적으로 원하므로, Eco는 top-down으로 형성 가능. 단 앵커 수요가 자체 ASIC(TPU·Trainium)로 새면 Qualcomm 몫이 소멸

---

## Claude 반론 (append-only, 반영 후)

1. **인과 방향 보정 반영** — "SRAM으로 Prefill을 대응"은 SRAM이 Prefill을 해결한다기보다, Prefill이 compute-bound라 큰 메모리가 애초에 불필요하고 그 빈자리를 SRAM이 값싸게 채우는 포지션. 이번 정리에서 "Compute-bound는 SRAM으로 대응"으로 보정됨. ✅
2. **HBM 배제 강도 — 천의 재반론 채택** : Claude는 "HBM을 넣으면 CoWoS 통행세로 회귀하므로 연결 아키텍처에서 HBM은 의도적 배제 대상"이라 주장했으나, **천 지적대로 HBM 배제는 timeline상 이번 제품에 한정된 선택이거나 특정 고객 요청일 가능성**이 있음. 따라서 "HBM 영구 배제"는 단정 불가 → 아키텍처에 HBM을 포함/제외 전환 가능한 유연성을 열어두는 게 타당. **미해결 쟁점으로 남김.**

## 미해결 쟁점 (다음 파기)

- [ ] Qualcomm이 실제로 무엇으로 HBM을 대체하는지 (기술 실체 검증 — 검색 필요)
- [ ] HBM 배제가 영구 전략인가 vs 이번 제품·특정 고객 한정인가
- [ ] SRAM/LPDDR/(HBM) 연결 아키텍처의 구체 구조

## 용어 각주

- **Prefill** : 프롬프트 전체를 병렬 처리하는 추론 초기 단계 (compute-bound)
- **Decode** : 토큰을 하나씩 순차 생성하는 단계 (memory-bound)
- **연산 강도(Arithmetic Intensity)** : 읽은 1바이트당 연산량(FLOPs/byte). 高→compute-bound, 低→memory-bound
- **GEMM / GEMV** : 행렬×행렬 / 행렬×벡터. Prefill=GEMM(재사용多), Decode=GEMV(재사용無)
- **SRAM** : 칩 내부 초고속·저전력 메모리. 수십 MB, TB/s급. Prefill 활성값 스크래치패드
- **LPDDR** : 저전력 오프칩 DRAM. 대역폭↓, GB당 가격·전력↓ → 대용량 유리
- **HBM** : D램 수직 적층 초광대역폭 메모리. 비싸고 TSMC CoWoS 캐파 종속
- **KV캐시** : Decode 중 누적되는 과거 토큰 상태값. 시퀀스 길수록 용량 압박
- **Batch** : 여러 요청 묶어 가중치 읽기 1회 공유. Decode 연산 강도↑ (amortize)
- **TCO / tokens-per-sec-per-$** : 단일 지연이 아닌 요청 묶음당 총비용 관점 지표
- **Roofline** : 연산 강도별 성능 상한이 대역폭 vs 연산 어디에 걸리는지 보는 분석 모델
