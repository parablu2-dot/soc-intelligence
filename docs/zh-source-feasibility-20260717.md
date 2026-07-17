---
date: 2026-07-17
topic: 중국어권(zh) 기사 소스 — Baidu 추가 기술 타당성 조사
status: 불가 판정, 대안 제시
---

# Baidu 뉴스/검색 소스 추가 — 타당성 조사 결과

## 배경

`SoC-Intelligence-Dashboard_Session_20260717.md` 작업지시서 항목 4: "중국어권(zh) 기사 소스로 Baidu 추가가
기술적으로 가능한지 조사하고, 가능하면 추가, 불가능하면 사유 보고 + 대안 제시."

## 현재 상태 — "중국어권" 탭은 실제로는 회사명 매칭일 뿐, 진짜 zh 소스가 아님

`site/js/app.js`의 `CHINESE_SOURCES` (기존 코드):
```js
const CHINESE_SOURCES = ['DigiTimes','Unisoc','MediaTek','SMIC','JCET'];
```
이 5개 소스는 전부 **영어** IR/뉴스 페이지를 크롤링한다(`crawlers/foundry/smic.py` 등 확인).
회사명이 아시아권이라는 이유로 "중국어권" 탭에 배치된 것일 뿐, 실제 중국어 텍스트 신호는 현재 하나도 없다.

한국어(KO) 소스는 `crawlers/foundry/etnews.py`가 실제 언어 태그(`_LANG_TAG = "KO"`)를 부여하는
정석 패턴을 이미 갖추고 있다 — Baidu를 붙인다면 이 패턴을 따라야 한다.

## 조사 결과

1. **`baidu.com/robots.txt`** (직접 fetch 확인):
   - `Disallow: /s?` — 검색결과 페이지(`baidu.com/s?wd=...`) 자체를 명시적으로 차단.
   - 파일 마지막에 미등록 User-agent 전체를 대상으로 한 catch-all `Disallow: /`.
   - `Baiduspider`(바이두 자사 크롤러)만 일부 예외(`/shifen/`, `/homepage/`, `/cpro` 등)를 받고,
     Googlebot을 포함한 그 외 모든 크롤러는 10개 이상의 Disallow 규칙 + catch-all로 사실상 전면 차단.
2. **`news.baidu.com/robots.txt`**: 직접 fetch 시 HTTP 500(서버 자체 오류)로 확인 실패. 별개로
   Baidu 뉴스는 애그리게이터 구조라 기사 본문이 각 언론사 사이트로 아웃링크되는 형태이며, 목록
   페이지 자체도 JS 렌더링 의존도가 높아 정적 파싱이 불안정하다(기존 크롤러들은 전부 정적 HTML/RSS
   파싱 기반, `crawlers/common/base_crawler.py`의 `fetch()`/`parse()` 인터페이스가 이를 전제로 함).
3. **공식 API/RSS**: 구글 뉴스 RSS(`crawlers/{axis}/googlenews.py`가 이미 사용 중)에 대응하는
   공식 무료 API나 로그인 없이 접근 가능한 피드가 Baidu에는 없음.

## 판정: 불가능

- **robots.txt 전면 차단** — 결정론적 정적 크롤러(`runtime-token-zero` 원칙, LLM 미개입 크롤링)로
  robots.txt를 무시하고 우회 크롤링하는 것은 이 프로젝트의 원칙(정적/합법적 수집)에 위배됨.
- **공식 API/로그인 없는 접근 경로 없음** — CLAUDE.md 규칙 2번(`BaseCrawler` 상속 + 정적 fetch/parse)에
  맞는 안정적인 구현 경로가 없음.

## 대안 제시

진짜 "zh 언어 신호"가 필요하다면, 이미 구축된 인프라를 재사용하는 두 가지 경로가 있다(이번 세션에서는
구현하지 않음 — 신규 소스 추가는 CLAUDE.md 규칙 2번에 따라 별도 diff·별도 승인으로 진행 권장):

1. **Google News RSS 중국어 쿼리 변형** (권장) — 기존 `crawlers/{axis}/googlenews.py` 패턴을 복제해
   `hl=zh-CN&gl=CN&ceid=CN:zh` 파라미터로 중국어 결과를 받는 `googlenews_zh.py` 변형 추가.
   `etnews.py`의 `_LANG_TAG = "KO"`와 동일하게 `_LANG_TAG = "ZH"`를 부여하면 되므로 구현 리스크가 낮음.
2. **정적 RSS를 제공하는 개별 중국 매체** (예: 36Kr, 澎湃新闻 등) — 매체별로 robots.txt/RSS 유무를
   개별 확인 필요. Google News 방식보다 구현 비용이 높지만 소스 다양성은 더 확보됨.

어느 쪽이든 프론트 `app.js`의 `CHINESE_SOURCES` 매칭 방식(현재는 회사명 기반)을
`tags.includes('ZH')` 기준으로 바꿔야 실제 언어 기준 분류가 된다.

## 추가: 후속 세션에서 구현 완료 (2026-07-17)

사용자 확인 후 대안 1(Google News zh 쿼리 변형)을 **TechSignal 스키마**로 구현.
`crawlers/tech/googlenews_zh.py` — arxiv.py와 동일하게 axis/company 없는 별도 stratum.
실행 결과: 94건 수집, TSMC 실적/AI칩 수요/항저우 칩 허브 등 실제 관련성 높은 기사 확인.

TechSignal은 "기사" 탭(axis 기반 `allSignals`)에는 뜨지 않고, 지금까지 프론트에 전혀
노출되지 않던 arXiv 논문과 함께 신설 "정보 획득 채널" 모듈의 `_techSignalsPanel()`에서
별도 섹션으로 노출하기로 결정(사용자 선택 — RefinedSignal 전환도 고려했으나 지시대로
TechSignal 유지 + 전용 패널 신설).
