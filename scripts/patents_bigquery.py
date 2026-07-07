"""
scripts/patents_bigquery.py — 특허 소스 (Phase 5 후속, item 3).

크롤러가 아니라 GHA cron에서 BigQuery 공개 데이터셋(patents-public-data)을 직접 쿼리해
PatentSignal로 매핑한다. 뉴스·논문과 분리된 별도 stratum — dedup_gate 미거침
(data/refined/tech/ 는 dedup_gate.py의 ingestion 제외 대상, arxiv.py와 동일 취급).

diff: publication_date > last_run (기존 누적분의 최대 publication_date, 최초 실행은
      _DEFAULT_LOOKBACK_DAYS 만큼만 거슬러 올라가 전체 테이블 풀스캔을 피함).
누적: publication_number가 자연 유니크키라 URL 누적(arxiv.py)과 달리 그 자체로 idempotent.

비용 가드 (BigQuery on-demand는 스캔한 컬럼 바이트 기준 과금 — row 필터는 비용을 줄이지 않음):
  - SELECT는 필요 컬럼만 (SELECT * 금지)
  - 5축 CPC 매칭을 축별로 6번 쿼리하지 않고 CASE 한 번으로 축 태깅 — 반드시 1쿼리 유지

미검증 (첫 실행 후 튜닝 필요 — 실측 전 지식 기반 추정):
  - CPC axis 매핑 우선순위: H01L25가 packaging·custom_soc 설계상 양쪽에 걸쳐 있어 임시로
    custom_soc 우선(코드 내 CASE 순서 참고). G06N도 hpc_datacenter·custom_soc 양쪽 앵커라
    바깥쪽(hpc_datacenter)으로 기본 배정.
  - google_patents_research.publications의 top_terms 컬럼 스키마 — 실패해도 본 파이프라인은
    계속되도록 별도 함수로 격리(_fetch_top_terms).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crawlers.common.schema import PatentSignal

OUT_PATH = ROOT / "data" / "refined" / "tech" / "patents.json"
_DEFAULT_LOOKBACK_DAYS = 90
_ROW_LIMIT = 5000

# 축별 CPC 앵커 (설계 릴레이 원안). H01L25/G06N 중복은 CASE 우선순위로 임시 해소.
_MAIN_QUERY = """
SELECT
  publication_number,
  (SELECT name FROM UNNEST(assignee_harmonized) LIMIT 1) AS assignee_harmonized,
  ARRAY(SELECT code FROM UNNEST(cpc)) AS cpc,
  filing_date,
  publication_date,
  (SELECT text FROM UNNEST(title_localized) WHERE language = 'en' LIMIT 1) AS title,
  (SELECT text FROM UNNEST(abstract_localized) WHERE language = 'en' LIMIT 1) AS abstract,
  CASE
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'H01L21')) THEN 'foundry'
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'H01L27')) THEN 'mobile_ap'
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'H01G')) THEN 'component_intelligence'
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'H01L23') OR STARTS_WITH(c.code, 'H01L24')) THEN 'packaging'
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'H01L25')) THEN 'custom_soc'
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'G06F15')) THEN 'hpc_datacenter'
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'G06F')) THEN 'mobile_ap'
    WHEN EXISTS(SELECT 1 FROM UNNEST(cpc) c WHERE STARTS_WITH(c.code, 'G06N')) THEN 'hpc_datacenter'
    ELSE NULL
  END AS axis
FROM `patents-public-data.patents.publications`
WHERE publication_date > @last_run
  AND EXISTS (
    SELECT 1 FROM UNNEST(cpc) c
    WHERE STARTS_WITH(c.code, 'G06F') OR STARTS_WITH(c.code, 'G06N')
       OR STARTS_WITH(c.code, 'H01L21') OR STARTS_WITH(c.code, 'H01L23')
       OR STARTS_WITH(c.code, 'H01L24') OR STARTS_WITH(c.code, 'H01L25')
       OR STARTS_WITH(c.code, 'H01L27') OR STARTS_WITH(c.code, 'H01G')
  )
ORDER BY publication_date DESC
LIMIT @row_limit
"""

_TOP_TERMS_QUERY = """
SELECT publication_number, top_terms
FROM `patents-public-data.google_patents_research.publications`
WHERE publication_number IN UNNEST(@pub_numbers)
"""


def _yyyymmdd_to_iso(n) -> str | None:
    if not n:
        return None
    s = str(int(n))
    if len(s) != 8:
        return None
    return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"


def _load_existing() -> list[dict]:
    if not OUT_PATH.exists():
        return []
    try:
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _last_run(existing: list[dict]) -> int:
    """existing의 최대 publication_date를 YYYYMMDD int로. 없으면 lookback 기본값."""
    dates = [r["publication_date"] for r in existing if r.get("publication_date")]
    if dates:
        return int(max(dates).replace("-", ""))
    lookback = date.today() - timedelta(days=_DEFAULT_LOOKBACK_DAYS)
    return int(lookback.strftime("%Y%m%d"))


def _get_client():
    sa_json = os.environ.get("GCP_SA_KEY")
    project = os.environ.get("GCP_PROJECT")
    if not sa_json or not project:
        return None

    from google.cloud import bigquery
    from google.oauth2 import service_account

    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(info)
    return bigquery.Client(project=project, credentials=creds)


def _fetch_top_terms(client, pub_numbers: list[str]) -> dict[str, list[str]]:
    """tentative — google_patents_research 스키마 미검증이라 실패해도 본 파이프라인은 계속됨."""
    if not pub_numbers:
        return {}
    try:
        from google.cloud import bigquery
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("pub_numbers", "STRING", pub_numbers),
            ]
        )
        rows = client.query(_TOP_TERMS_QUERY, job_config=job_config).result()
        return {r["publication_number"]: list(r["top_terms"] or []) for r in rows}
    except Exception as exc:
        print(f"::warning::top_terms fetch skipped (google_patents_research 스키마 미검증): {exc}")
        return {}


def run() -> None:
    client = _get_client()
    if client is None:
        print("::warning::GCP_SA_KEY/GCP_PROJECT 미설정 — 특허 소스 스킵")
        return

    from google.cloud import bigquery

    existing = _load_existing()
    seen = {r["publication_number"] for r in existing if r.get("publication_number")}
    last_run = _last_run(existing)

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("last_run", "INT64", last_run),
            bigquery.ScalarQueryParameter("row_limit", "INT64", _ROW_LIMIT),
        ]
    )
    print(f"[patents_bigquery] querying publication_date > {last_run}")
    rows = list(client.query(_MAIN_QUERY, job_config=job_config).result())
    print(f"[patents_bigquery] {len(rows)} rows returned")

    new_pub_numbers = [r["publication_number"] for r in rows if r["publication_number"] not in seen]
    top_terms_map = _fetch_top_terms(client, new_pub_numbers)

    added = 0
    for r in rows:
        pub_num = r["publication_number"]
        if not pub_num or pub_num in seen:
            continue
        if not r["axis"]:
            continue  # WHERE에서 이미 매칭된 건만 통과시켰으니 이례적 — 방어적 skip

        pub_date_iso = _yyyymmdd_to_iso(r["publication_date"])
        filing_date_iso = _yyyymmdd_to_iso(r["filing_date"]) or pub_date_iso
        if not pub_date_iso:
            continue

        try:
            sig = PatentSignal(
                publication_number=pub_num,
                assignee_harmonized=r["assignee_harmonized"] or "",
                cpc=list(r["cpc"] or []),
                filing_date=date.fromisoformat(filing_date_iso),
                publication_date=date.fromisoformat(pub_date_iso),
                title=r["title"] or "",
                abstract=(r["abstract"] or "")[:1000],
                axis=r["axis"],
                url=f"https://patents.google.com/patent/{pub_num}",
                top_terms=top_terms_map.get(pub_num, []),
            )
        except Exception as exc:
            print(f"::warning::skip {pub_num}: {exc}")
            continue

        existing.append(sig.to_dict())
        seen.add(pub_num)
        added += 1

    existing.sort(key=lambda r: r.get("publication_date", ""), reverse=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[patents_bigquery] added={added} total={len(existing)} → {OUT_PATH}")


if __name__ == "__main__":
    run()
