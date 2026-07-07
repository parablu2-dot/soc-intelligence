---
type: DistillationNote
axis: component-intelligence
customer: [삼성전기, 무라타]
status: design-baseline
tags: [수요의소유, 응고점, bom_implication]
---

# SoC Dashboard 확장 — 부품·기판 수요 인텔리전스

> 잠재 고객: 삼성전기 / 무라타 Market Intelligence 담당자
> 성격: 칩 경쟁 인텔이 아니라, downstream 디바이스/칩셋 수요 → 부품·기판 수요 **파생(derivation)** 인텔

## 1. 설계 원칙 (기존 구조 불변)

- 파이프라인(crawl→dedup→distill→commit→deploy) **변경 0**
- 매핑은 static → **runtime-token-zero 유지**, LLM은 distill 시점에 규칙 적용만
- facts / inferences 분리 원칙에 그대로 얹음 (bom_implication은 inference 하위)
- append-only

## 2. 스키마 추가분 (필드 2개만)

```yaml
bom_implication:
  - component_group: MLCC | substrate | module | inductor | silicon_cap | glass_substrate
    device_axis:     server | mobile | pc
    direction:       up | down | neutral
    basis_fact_id:   <facts[] 참조>
    strength_hint:   strong | moderate | weak        # 정성. 유닛 예측 X
    derivation_type: content | leading | near_fact | transition
```

**derivation_type 의미 (축마다 파생 성격이 다름)**

| type | 뜻 | 해당 축 |
|---|---|---|
| content | 디바이스 고성능화 → 대당 부품 content ↑ | Mobile AP, 서버, Custom SoC |
| leading | 미래 물량 **선행 신호** (dir 아님) | Foundry |
| near_fact | 고객이 직접 앉은 레이어, 파생거리 0 | Packaging |
| transition | 기술 **전환 응고점** 추적 (신사업 베팅 검증) | Silicon Cap, 유리기판 |

## 3. 축 매핑 — 신규 추가는 실질 3개

| 고객 디바이스축 | 기존 축 | 처리 |
|---|---|---|
| 모바일 device | Mobile AP | device-facing 리네이밍만 |
| 서버 | HPC·DC | 그대로 (최고가치) |
| AI 칩셋 | Custom SoC + HPC·DC | 이미 커버 |
| PC / Client | — | **신규 추가** |
| — | Foundry | 유지 (공급 선행지표 = 차별점) |
| — | Packaging | 유지 (부품·기판 브릿지 = 고객 핵심) |

→ 기존 5축 대부분은 이름만 다름. 실질 신규는 **PC축 + 신사업 2종(Si Cap·유리기판)**.

## 4. bom_implication 규칙 — 5축

### 서버 (HPC·DC) — PoC 1순위

| # | basis_fact | component | dir | str | type |
|---|---|---|---|---|---|
| 1 | AI 가속기 세대전환 (HBM 스택↑, TDP↑) | MLCC(고용량·고전압) | up | strong | content |
| 2 | GPU 패키지 대형화 (2.5D/CoWoS 면적↑) | substrate(ABF 층수·면적) | up | strong | content |
| 3 | 서버 전력밀도↑ → 고전류 전원단 | inductor/power | up | moderate | content |
| 4 | 랙 단위 수랭 (rack-scale) | module | up | moderate | content |
| 5 | **CPU/범용 서버 리프레시 회복 + AI 대당 content 급증** | MLCC | up | moderate | content |

> #5 주석: **대수 드라이버(CPU서버 회복) × 대당-content 드라이버(AI서버) 분리**가 핵심.
> 대수 트렌드는 시황 수치 → 최신치 검색 확인 필요(현재 미확인).

### Mobile AP — content

| basis_fact | component | dir | str |
|---|---|---|---|
| 온디바이스 AI(NPU) 강화 → 전력·전송↑ | MLCC(소형·고용량) | up | moderate |
| 폴더블/슬림 폼팩터 | substrate(SLP/mSAP) | up | moderate |
| 카메라 모듈 고도화 (삼성전기 직결) | module | up | moderate |

### Custom SoC — content

| basis_fact | component | dir | str |
|---|---|---|---|
| 하이퍼스케일러 ASIC 확산 | substrate(대면적 ABF) | up | strong |
| 칩렛·다이 수↑ → I/O↑ | substrate/interposer | up | strong |
| 전원 무결성 요구↑ | MLCC(패키지 근접) | up | strong |

### Foundry — leading (dir 아님, 선행지표 태그)

| basis_fact | 해석 | str |
|---|---|---|
| 선단노드 capa·가동률↑ | 전 부품군 물량 선행 신호 | moderate |
| 노드 전환(GAA) | 패키지 복잡도↑ → substrate | moderate |

### Packaging — near_fact (고객 직접 레이어)

| basis_fact | component | dir | str |
|---|---|---|---|
| 패널레벨/2.5D 확산 | substrate 직접 수요 | up | strong |
| 하이브리드 본딩 | material/substrate 사양변화 | up | strong |

## 5. 신사업 축 — transition (응고점 추적)

> 이 두 축은 "수요 파생"이 아니라 **고객의 전환 베팅 검증**.
> 질문: "언제 전환이 응고되나" → MI 담당자 capex·R&D 의사결정 직결. 최고가치.

### Silicon Capacitor (실리콘 커패시터)

- **정의**: 실리콘에 deep-trench로 형성한 커패시터. MLCC 대비 초소형·저프로파일·저ESL·고주파 안정·고온 신뢰성
- **적용**: AI 가속기/AP 패키지 **내장(embedded)**, PoL 전원 근접 디커플링, HBM 인근
- **고객 포지션**: 무라타 = IPDiA 인수로 선점 / 삼성전기 = 신사업 개발
- **인텔 초점**: MLCC → Si Cap **전환 응고점**

| basis_fact | component | dir | str | type |
|---|---|---|---|---|
| AI 가속기 전원무결성 요구 극한화 | silicon_cap | up | strong | transition |
| 패키지 내장(IVR/embedded) 확산 | silicon_cap | up | strong | transition |
| MLCC로 커버되던 고주파 대역 이탈 | MLCC(잠식) | down | weak | transition |

### 유리기판 (Glass Substrate)

- **정의**: 유리 코어 기판. ABF(organic) 대비 저휨(low warpage)·대면적·미세피치·치수/열 안정
- **적용**: 대형 AI 패키지(다수 칩렛), 2.5D 이상, panel-level과 결합
- **고객 포지션**: 삼성전기 대규모 투자 / Absolics(SKC) / Intel 로드맵
- **인텔 초점**: ABF → Glass **전환 응고점** (Packaging near_fact이자 transition)

| basis_fact | component | dir | str | type |
|---|---|---|---|---|
| 대형 칩렛 패키지 면적·휨 한계 도달 | glass_substrate | up | moderate | transition |
| AI 가속기 세대전환(초대형 패키지) | glass_substrate | up | moderate | transition |
| ABF 공급/사양 한계 뉴스 | substrate(ABF 잠식) | down | weak | transition |

## 6. 프레임 연결 & track record

- **수요의 소유**: 수요를 device → component로 한 단 내려 소유권 추적 (content/near_fact 축)
- **응고점**: 신사업 2종의 전환 타이밍 = 판단 축 (transition 축)
- 각 파생 = 미래 부품수요 **projection** → 실적 대조로 점수화 → **검증된 판단 track record** 자본화

## 7. Next

- [ ] PoC: 서버(HPC·DC) 축 규칙 5개 실제 distill 적용
- [ ] 서버 대수 트렌드(CPU 회복 vs AI) 시황 수치 검증 — 검색
- [ ] transition 축 응고점 판정 기준(신호 임계값) 정의
- [ ] 겹치는 축부터 순차 확장 (지침: 겹치는 제품군 우선)
