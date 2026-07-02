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
# (company, node, year, month, wspm, usd_per_wafer, yield, is_forecast, source)
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
    ("tsmc", "N3/N3E", 2025,  1, 100_000, 21_500,  None, True,  "TrendForce forecast"),
    ("tsmc", "N3/N3E", 2026,  1, 115_000, 21_500,  None, True,  "TrendForce forecast"),

    # ══ TSMC N2 (2nm) ══ 2025년 양산 목표
    ("tsmc", "N2",   2025,  7,  20_000, 28_000,  None, True,  "TrendForce / SemiAnalysis forecast"),
    ("tsmc", "N2",   2026,  1,  50_000, 28_000,  None, True,  "TrendForce / SemiAnalysis forecast"),
    ("tsmc", "N2",   2026,  7,  80_000, 28_000,  None, True,  "TrendForce / SemiAnalysis forecast"),

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

    # ══ Intel Foundry 18A ══ 2025년 목표 (Intel 4는 내재화 위주)
    ("intel_foundry", "18A",  2025,  7,  10_000, 25_000,  None, True,  "Intel IR / SemiAnalysis forecast"),
    ("intel_foundry", "18A",  2026,  1,  25_000, 25_000,  None, True,  "Intel IR / SemiAnalysis forecast"),

    # ══ GlobalFoundries 12LP+ ══ 성숙 노드, 2021~
    ("globalfoundries", "12LP+", 2021,  1, 130_000, 5_200, 0.95, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2022,  1, 145_000, 5_500, 0.95, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2023,  1, 150_000, 5_700, 0.96, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2024,  1, 148_000, 5_700, 0.96, False, "SEMI / GF IR estimate"),
    ("globalfoundries", "12LP+", 2025,  1, 145_000, 5_700,  None, True,  "SEMI forecast"),

    # ══ TSMC CoWoS-L (첨단 패키징) ══ packaging 축
    ("tsmc", "CoWoS-L", 2022,  1,   3_000,  None, None, False, "TrendForce / Bloomberg estimate"),
    ("tsmc", "CoWoS-L", 2023,  1,   7_000,  None, None, False, "TrendForce / Bloomberg estimate"),
    ("tsmc", "CoWoS-L", 2024,  1,  15_000,  None, None, False, "TrendForce / Bloomberg estimate"),
    ("tsmc", "CoWoS-L", 2025,  1,  25_000,  None, None, True,  "TrendForce forecast"),
    ("tsmc", "CoWoS-L", 2026,  1,  35_000,  None, None, True,  "TrendForce forecast"),
]


def build_records() -> list[FoundryCapacityRecord]:
    records = []
    for row in _RAW_DATA:
        company, node, year, month, wspm, price, yld, is_fc, source = row
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
            url="",
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
