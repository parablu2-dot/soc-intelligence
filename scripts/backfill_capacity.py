"""
FoundryCapacityRecord 백필 스크립트 (1회성 임포트).
CHANGES-v3 Phase 3 spec #10: 과거 3~5년 캐파 데이터를 채우고 이후 diff로만 갱신.

데이터 출처: 공개 애널리스트 보고서 추정치
  - TrendForce, SEMI, Bloomberg, Reuters 인용 수치를 paraphrase
  - 정확한 계약 수치가 아닌 업계 컨센서스 추정 (is_forecast=False: 과거, True: 미래)
  - 단위: wspm (wafer starts per month), USD/wafer (Fully Processed 기준)

실행:
  cd soc-intelligence
  python scripts/backfill_capacity.py
"""
import json
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crawlers.common.schema import FoundryCapacityRecord

OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "refined" / "foundry" / "capacity_records.json"

# ── 데이터 정의 ─────────────────────────────────────────────────────────────
# (company, node, year, month, wspm, usd_per_wafer, yield, is_forecast, source[, url])
# 갱신 규칙(2026-09-26~): 과거 월=실적(is_forecast=False), 미래 월=예측. 신규 수치가 나오면 같은 노드의
# 지난 예측 행은 삭제하고 실적/신규 예측으로 교체 (오래된 예측이 '최신 예측'으로 남지 않게)
# wspm: 단위 1000wspm (실제 값 * 1000)
# yield: None = 비공개 / float 0.0~1.0
# Ref: TrendForce quarterly reports, SEMI World Fab Watch, Bloomberg industry reports

_RAW_DATA = [
    # ══ TSMC N7 (7nm) ══ 2019년 양산 개시, 2021~2023 성숙기
    ("tsmc", "N7",  2021,  1, 210_000, 9_346, 0.92, False, "TrendForce / SEMI estimate"),
    ("tsmc", "N7",  2021,  7, 215_000, 9_346, 0.93, False, "TrendForce / SEMI estimate"),
    ("tsmc", "N7",  2022,  1, 220_000, 9_800, 0.93, False, "TrendForce / SEMI estimate"),
    ("tsmc", "N7",  2022,  7, 218_000, 9_800, 0.93, False, "TrendForce / SEMI estimate"),
    ("tsmc", "N7",  2023,  1, 215_000, 9_950, 0.94, False, "TrendForce / SEMI estimate"),
    ("tsmc", "N7",  2023,  7, 210_000, 9_950, 0.94, False, "TrendForce / SEMI estimate"),
    ("tsmc", "N7",  2024,  1, 205_000, 9_950, 0.94, False, "TrendForce / SEMI estimate"),
    ("tsmc", "N7",  2025,  1, 195_000, 9_950,  None, True,  "TrendForce forecast"),
    ("tsmc", "N7",  2026,  1, 185_000, 9_950,  None, True,  "TrendForce forecast"),

    # ══ TSMC N5/N4 (5/4nm) ══ 2020년 양산 개시
    ("tsmc", "N5/N4", 2021,  1,  60_000, 14_000, 0.78, False, "Bloomberg / TrendForce estimate"),
    ("tsmc", "N5/N4", 2021,  7,  85_000, 14_000, 0.82, False, "Bloomberg / TrendForce estimate"),
    ("tsmc", "N5/N4", 2022,  1, 110_000, 15_500, 0.85, False, "Bloomberg / TrendForce estimate"),
    ("tsmc", "N5/N4", 2022,  7, 130_000, 15_500, 0.87, False, "Bloomberg / TrendForce estimate"),
    ("tsmc", "N5/N4", 2023,  1, 150_000, 16_200, 0.89, False, "Bloomberg / TrendForce estimate"),
    ("tsmc", "N5/N4", 2023,  7, 155_000, 16_200, 0.90, False, "Bloomberg / TrendForce estimate"),
    ("tsmc", "N5/N4", 2024,  1, 160_000, 16_500, 0.91, False, "Bloomberg / TrendForce estimate"),
    ("tsmc", "N5/N4", 2025,  1, 165_000, 16_500,  None, True,  "TrendForce forecast"),

    # ══ TSMC N3/N3E (3nm) ══ 2022H2 양산 개시
    ("tsmc", "N3/N3E", 2022,  7,   8_000, 20_000, 0.55, False, "Bloomberg / Reuters estimate"),
    ("tsmc", "N3/N3E", 2023,  1,  20_000, 20_000, 0.65, False, "Bloomberg / Reuters estimate"),
    ("tsmc", "N3/N3E", 2023,  7,  45_000, 20_500, 0.72, False, "Bloomberg / Reuters estimate"),
    ("tsmc", "N3/N3E", 2024,  1,  65_000, 21_000, 0.78, False, "Bloomberg / Reuters estimate"),
    ("tsmc", "N3/N3E", 2024,  7,  85_000, 21_000, 0.82, False, "Bloomberg / Reuters estimate"),
    # 2026-09 갱신: 2025말 120~130K → 1H26 ~150K → 4Q26초 180K(예정보다 2~3개월 앞당김) → 2027 중반 210K
    ("tsmc", "N3/N3E", 2025, 12, 125_000, 19_500,  None, False, "TrendForce 2026-04 (2025말 120~130K)", "https://www.trendforce.com/news/2026/04/27/news-tsmc-3nm-monthly-capacity-may-hit-180k-wafers-by-2026-up-over-40-yoy-on-ai-demand/"),
    ("tsmc", "N3/N3E", 2026,  6, 150_000, 20_000,  None, False, "TrendForce 2026-08 (1H26 ~150K) / 가격 SiliconAnalysts 2026-08", "https://www.trendforce.com/news/2026/08/03/news-tsmc-3nm-monthly-wafer-starts-to-hit-180k-by-early-4q26-on-strong-demand-2-3-months-ahead-of-expectations/"),
    ("tsmc", "N3/N3E", 2026, 10, 180_000, 20_000,  None, True,  "TrendForce 2026-08 (4Q26초 180K, 2H26 최대 15% 인상 검토)", "https://www.trendforce.com/news/2026/08/03/news-tsmc-3nm-monthly-wafer-starts-to-hit-180k-by-early-4q26-on-strong-demand-2-3-months-ahead-of-expectations/"),
    ("tsmc", "N3/N3E", 2027,  6, 210_000,  None,   None, True,  "TrendForce 2026-09 (2027 중반 210K)", "https://www.trendforce.com/news/2026/09/14/news-tsmc-reportedly-targets-22-2nm-16-3nm-capacity-boost-by-mid-2027-cowos-to-double-by-2028"),

    # ══ TSMC N2 (2nm) ══ 2025년 양산 목표
    # 2026-09 갱신: 4Q25 양산 개시, 2025말 45~50K → 1H26 50~60K → 연말 90K(9월 하향, 이전 100~140K) → 2027 중반 110K
    ("tsmc", "N2",   2025, 12,  47_500, 30_000,  None, False, "TrendForce 2025-08 (2025말 45~50K, 3nm 대비 +50% 가격)", "https://www.trendforce.com/news/2025/08/05/news-tsmcs-2nm-node-reportedly-set-for-60k-monthly-output-in-2026-with-prices-50-above-3nm/"),
    ("tsmc", "N2",   2026,  6,  55_000, 30_000,  None, False, "TrendForce 2026-08 (1H26 50~60K)", "https://www.trendforce.com/news/2026/08/03/news-tsmc-3nm-monthly-wafer-starts-to-hit-180k-by-early-4q26-on-strong-demand-2-3-months-ahead-of-expectations/"),
    ("tsmc", "N2",   2026, 12,  90_000, 30_000,  None, True,  "TrendForce 2026-09 (연말 90K, 이전 추정 100K에서 하향)", "https://www.trendforce.com/news/2026/09/14/news-tsmc-reportedly-targets-22-2nm-16-3nm-capacity-boost-by-mid-2027-cowos-to-double-by-2028"),
    ("tsmc", "N2",   2027,  6, 110_000,  None,   None, True,  "TrendForce 2026-09 (2027 중반 110K)", "https://www.trendforce.com/news/2026/09/14/news-tsmc-reportedly-targets-22-2nm-16-3nm-capacity-boost-by-mid-2027-cowos-to-double-by-2028"),

    # ══ Samsung Foundry 4nm (4LPE/4LPP) ══ 2021년 양산 개시
    ("samsung_foundry", "4nm",  2022,  1,  40_000, 13_500, 0.68, False, "DigiTimes / TrendForce estimate"),
    ("samsung_foundry", "4nm",  2022,  7,  50_000, 13_500, 0.72, False, "DigiTimes / TrendForce estimate"),
    ("samsung_foundry", "4nm",  2023,  1,  60_000, 14_000, 0.75, False, "DigiTimes / TrendForce estimate"),
    ("samsung_foundry", "4nm",  2023,  7,  65_000, 14_000, 0.77, False, "DigiTimes / TrendForce estimate"),
    ("samsung_foundry", "4nm",  2024,  1,  70_000, 14_500, 0.80, False, "DigiTimes / TrendForce estimate"),
    ("samsung_foundry", "4nm",  2025,  1,  75_000, 14_500,  None, True,  "TrendForce forecast"),

    # ══ Samsung Foundry 3GAE (3nm GAA) ══ 2022년 양산 개시
    ("samsung_foundry", "3GAE", 2022,  7,   5_000, 18_000, 0.40, False, "Reuters / Bloomberg estimate"),
    ("samsung_foundry", "3GAE", 2023,  1,  10_000, 18_000, 0.52, False, "Reuters / Bloomberg estimate"),
    ("samsung_foundry", "3GAE", 2023,  7,  18_000, 18_500, 0.60, False, "Reuters / Bloomberg estimate"),
    ("samsung_foundry", "3GAE", 2024,  1,  25_000, 19_000, 0.65, False, "Reuters / Bloomberg estimate"),
    ("samsung_foundry", "3GAE", 2025,  1,  35_000, 19_500,  None, True,  "TrendForce forecast"),
    ("samsung_foundry", "3GAE", 2026,  1,  50_000, 19_500,  None, True,  "TrendForce forecast"),


    # ══ Samsung Foundry SF2 (2nm GAA) ══ 2025말 양산(Exynos 2600), 2026-09 추가
    # 캐파 실측 공개 없음 → 수율/가격만 실적, 캐파는 연말 목표(DigiTimes)만 예측으로 기재
    ("samsung_foundry", "SF2", 2026,  1,    None, 20_000, 0.50, False, "Exynos 2600 수율 ~50%(SammyFans) / 가격 인하 $20K(SemiWiki)", "https://www.sammyfans.com/2026/01/15/samsung-improves-2nm-exynos-2600-yields/"),
    ("samsung_foundry", "SF2", 2026, 12,  21_000, 20_000,  None, True,  "DigiTimes 2025-11 (2026말 21K 목표, Taylor는 2027 SF2P+ 고객 양산)", "https://www.digitimes.com/news/a20251121PD240/samsung-2026-tsmc-2nm-qualcomm.html"),

    # ══ Intel Foundry 18A ══ 2025년 목표 (Intel 4는 내재화 위주)
    # 2026-09 갱신: Fab 52 HVM(Panther Lake), 합산 ~30K wspm 보도. 수율은 "정상 마진엔 미달, 업계 표준 도달은 2027"(Tom's Hardware) → 수치 미기재
    ("intel_foundry", "18A",  2026,  6,  30_000,  None,  None, False, "Intel 18A 램프 보도 종합(신뢰도 중)", "https://www.kad8.com/ai/intel-reports-18a-yield-breakthrough-30000-wafers-per-month-capacity-and-14a-roadmap/"),

    # ══ GlobalFoundries 12LP+ ══ 성숙 노드, 2021~
    ("globalfoundries", "12LP+", 2021,  1, 130_000, 5_200, 0.95, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2022,  1, 145_000, 5_500, 0.95, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2023,  1, 150_000, 5_700, 0.96, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2024,  1, 148_000, 5_700, 0.96, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2025,  1, 145_000, 5_700,  None, True,  "SEMI forecast"),

    # ══ GlobalFoundries 전사 (300mm 환산) ══ 노드별 공개 없음 — 분기 출하 625K ÷ 3, 가동률 high-80% (Q2 2026 IR)
    ("globalfoundries", "전사(300mm eq)", 2026,  6, 208_000,  None, None, False, "GF Q2 2026 실적 (분기 출하 ~625K 300mm eq)", "https://investors.gf.com/news-releases/news-release-details/globalfoundries-reports-second-quarter-2026-financial-results"),

    # ══ SMIC 7nm급 (N+2, DUV 멀티패터닝) ══ 2026-09 추가
    ("smic", "7nm급(N+2)", 2025, 12,  45_000,  None,  None, False, "TrendForce 2025-08 (7nm 이하 2025말 ~45K)", "https://www.trendforce.com/news/2025/08/29/news-smic-1h25-net-profit-rises-35-6-7nm-capacity-reportedly-to-double-in-2026/"),
    ("smic", "7nm급(N+2)", 2026, 12,  60_000,  None,  None, True,  "TrendForce 2025-08 (2026 60K, 2배 증설 계획)", "https://www.trendforce.com/news/2025/08/29/news-smic-1h25-net-profit-rises-35-6-7nm-capacity-reportedly-to-double-in-2026/"),

    # ══ TSMC CoWoS (S/L/R 합산, 첨단 패키징) ══ packaging 축
    ("tsmc", "CoWoS", 2022,  1,   3_000,  None, None, False, "TrendForce / Bloomberg estimate"),
    ("tsmc", "CoWoS", 2023,  1,   7_000,  None, None, False, "TrendForce / Bloomberg estimate"),
    ("tsmc", "CoWoS", 2024,  1,  15_000,  None, None, False, "TrendForce / Bloomberg estimate"),
    # 2026-09 갱신: 2025말 70~75K → 2026말 ~130K(공급부족 20%→10%) → 2028말 260K(2배)
    ("tsmc", "CoWoS", 2025, 12,  72_500,  None, None, False, "TrendForce 2025-01 (2025 70~75K)", "https://www.trendforce.com/news/2025/01/02/news-tsmc-set-to-expand-cowos-capacity-to-record-75000-wafers-in-2025-doubling-2024-output/"),
    ("tsmc", "CoWoS", 2026, 12, 130_000,  None, None, True,  "TrendForce 2026-09 (2026말 ~130K)", "https://www.trendforce.com/news/2026/09/14/news-tsmc-reportedly-targets-22-2nm-16-3nm-capacity-boost-by-mid-2027-cowos-to-double-by-2028"),
    ("tsmc", "CoWoS", 2028, 12, 260_000,  None, None, True,  "TrendForce 2026-09 (2028말 260K, AP7·Arizona 증설)", "https://www.trendforce.com/news/2026/09/14/news-tsmc-reportedly-targets-22-2nm-16-3nm-capacity-boost-by-mid-2027-cowos-to-double-by-2028"),
]


def build_records() -> list[FoundryCapacityRecord]:
    records = []
    for row in _RAW_DATA:
        company, node, year, month, wspm, price, yld, is_fc, source = row[:9]
        url = row[9] if len(row) > 9 else ""
        # axis 결정: CoWoS는 packaging, 나머지는 foundry
        axis = "packaging" if "CoWoS" in node or "InFO" in node else "foundry"
        records.append(FoundryCapacityRecord(
            axis=axis,
            company=company,
            node=node,
            month=f"{year:04d}-{month:02d}",
            wafer_capacity=wspm,
            price_per_wafer=float(price) if price is not None else None,
            yield_rate=yld,
            is_forecast=is_fc,
            source=source,
            url=url,
        ))
    return records


def main():
    records = build_records()
    # 월 기준 정렬
    records.sort(key=lambda r: (r.company, r.node, r.month))
    out_data = [r.to_dict() for r in records]
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"capacity_records.json 생성: {len(out_data)}건 → {OUT_PATH}")

    # 요약 출력
    by_company = {}
    for r in records:
        key = f"{r.company}/{r.node}"
        by_company.setdefault(key, {"hist": 0, "fc": 0})
        if r.is_forecast:
            by_company[key]["fc"] += 1
        else:
            by_company[key]["hist"] += 1
    for key, cnt in sorted(by_company.items()):
        print(f"  {key}: 과거 {cnt['hist']}건 / 예측 {cnt['fc']}건")


if __name__ == "__main__":
    main()
