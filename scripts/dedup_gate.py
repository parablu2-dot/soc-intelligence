"""
dedup_gate.py — 임베딩 dedup 게이트

입력 : data/refined/{axis}/*.json  (크롤러 RefinedSignal 출력)
출력 : SQLite raw_documents + canonical_nodes + merge_log 갱신

판정 순서 (고정):
  1. 엔티티 추출 (company + 공정 노드 + 주요 제품)
  2. 엔티티 불일치 → 유사도 무관하게 new  (false merge 방어)
  3. 엔티티 일치 + 코사인 유사도 ≥ threshold → merged
  4. 그 외 → new

원칙 : 빌드타임 전용. 벡터 상시 캐시 없음.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml

from scripts.db.db import (
    get_conn, init_db,
    insert_raw, insert_canonical, update_canonical,
    insert_merge_log, get_unprocessed_raws, get_all_canonical,
)

DATA_REFINED = ROOT / "data" / "refined"

# ── 엔티티 목록 ────────────────────────────────────────────────────────────────
# 길이 내림차순 정렬 — 부분 매칭 방지 (n3e 를 n3 보다 먼저 확인)
_PROCESS_NODES: list[str] = sorted([
    "n2p", "n2", "n3e", "n3p", "n3", "n4p", "n4", "n5", "n6", "n7",
    "3nm", "2nm", "4nm", "5nm", "7nm", "10nm", "28nm",
    "18a", "20a", "12lp", "14nm",
    "sf2", "sf3", "sf4", "sf5", "3gae", "3gap",
], key=len, reverse=True)
_PROCESS_NODES_SET: frozenset[str] = frozenset(_PROCESS_NODES)

_PRODUCTS: frozenset[str] = frozenset([
    "cowos", "hbm3e", "hbm3", "hbm4", "ucie", "chiplet", "info_wlp",
])


# ── 엔티티 추출 / 비교 ─────────────────────────────────────────────────────────

def extract_entities(signal: dict) -> dict:
    """회사명 + 공정 노드 + 주요 제품을 추출해 dict 반환."""
    text = (
        (signal.get("headline") or signal.get("title", "")) + " " +
        " ".join(signal.get("tags") or [])
    ).lower()
    nodes = frozenset(n for n in _PROCESS_NODES if n in text)
    products = frozenset(p for p in _PRODUCTS if p in text)
    return {"company": signal.get("company", ""), "nodes": nodes, "products": products}


def entities_match(raw_e: dict, cand_e: dict) -> bool:
    """
    False merge 방어 규칙:
      - company 불일치 → False
      - 둘 다 공정 노드 정보 보유 + 교집합 없음 → False
    """
    if raw_e["company"] != cand_e["company"]:
        return False
    if raw_e["nodes"] and cand_e["nodes"] and not (raw_e["nodes"] & cand_e["nodes"]):
        return False
    return True


# ── ID 생성 ────────────────────────────────────────────────────────────────────

def _url_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:24]


# ── raw 인제스트 ───────────────────────────────────────────────────────────────

def _ingest_refined(conn) -> int:
    """data/refined/ RefinedSignal JSON → raw_documents (INSERT OR IGNORE)."""
    now = datetime.now(timezone.utc).isoformat()
    count = 0
    for jpath in DATA_REFINED.rglob("*.json"):
        if jpath.name == "capacity_records.json":
            continue
        try:
            records = json.loads(jpath.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(records, list):
            continue
        for rec in records:
            if not isinstance(rec, dict) or not rec.get("url"):
                continue
            insert_raw(conn, {
                "id": _url_id(rec["url"]),
                "crawled_at": now,
                "source": rec.get("source", ""),
                "axis": rec.get("axis", ""),
                "company": rec.get("company", ""),
                "title": rec.get("headline", rec.get("title", "")),
                "summary": rec.get("summary"),
                "url": rec["url"],
                "raw_json": json.dumps(rec, ensure_ascii=False),
            })
            count += 1
    return count


# ── canonical 생성 / 검증 갱신 ────────────────────────────────────────────────

def _make_canonical(raw: dict, signal: dict, entities: dict, ts: str) -> dict:
    all_keys = list(entities["nodes"] | entities["products"])
    return {
        "id": raw["id"],          # 최초 raw_id 그대로 사용 (stable)
        "axis": raw["axis"],
        "company": raw["company"],
        "entity_keys": json.dumps(all_keys, ensure_ascii=False),
        "title": raw["title"],
        "verification": json.dumps({
            "url": signal.get("url"),
            "source": signal.get("source"),
            "published_date": signal.get("published_date"),
            "category": signal.get("category"),
            "axis": signal.get("axis"),
            "company": signal.get("company"),
        }, ensure_ascii=False),
        "inference": json.dumps({
            "tags": signal.get("tags") or [],
            "summary": signal.get("summary"),
        }, ensure_ascii=False),
        "created_at": ts,
        "updated_at": ts,
    }


def _build_cand_entities(canonical: dict) -> dict:
    """canonical_nodes.entity_keys JSON → entities dict."""
    keys = json.loads(canonical["entity_keys"])
    return {
        "company": canonical["company"],
        "nodes": frozenset(k for k in keys if k in _PROCESS_NODES_SET),
        "products": frozenset(k for k in keys if k in _PRODUCTS),
    }


# ── 메인 ──────────────────────────────────────────────────────────────────────

def run() -> None:
    cfg = yaml.safe_load((ROOT / "crawlers" / "config.yaml").read_text(encoding="utf-8"))
    dedup_cfg = cfg.get("dedup", {})
    model_name: str = dedup_cfg.get("model", "all-MiniLM-L6-v2")
    threshold: float = float(dedup_cfg.get("threshold", 0.88))

    init_db()
    conn = get_conn()

    try:
        # 1. data/refined/ → raw_documents
        ingested = _ingest_refined(conn)
        conn.commit()
        print(f"[ingest]  {ingested} records scanned (INSERT OR IGNORE)")

        # 2. 미처리 raws
        unprocessed = [dict(r) for r in get_unprocessed_raws(conn)]
        print(f"[dedup]   {len(unprocessed)} unprocessed raws to evaluate")
        if not unprocessed:
            print("[done]    nothing to do")
            return

        # 3. 임베딩 모델 로드
        print(f"[embed]   loading {model_name} …")
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer(model_name)

        # 4. 기존 canonical 로드 (axis+company 키 딕셔너리)
        existing: dict[tuple, list] = defaultdict(list)
        for c in [dict(r) for r in get_all_canonical(conn)]:
            existing[(c["axis"], c["company"])].append(c)

        now_ts = datetime.now(timezone.utc).isoformat()
        stats: dict[str, int] = defaultdict(int)

        pending_canonicals: list[dict] = []
        merge_log_entries: list[dict] = []
        # (canonical_dict, new_signal_dict, ts) — merge_refine가 처리할 대상
        verification_updates: list[tuple] = []

        for raw in unprocessed:
            axis, company = raw["axis"], raw["company"]
            signal = json.loads(raw["raw_json"])
            raw_e = extract_entities(signal)

            candidates = existing.get((axis, company), [])

            if not candidates:
                # 후보 없음 → 무조건 new
                new_c = _make_canonical(raw, signal, raw_e, now_ts)
                pending_canonicals.append(new_c)
                existing[(axis, company)].append(new_c)
                merge_log_entries.append({
                    "raw_id": raw["id"],
                    "canonical_id": new_c["id"],
                    "similarity": None,
                    "decision": "new",
                    "entity_match": 0,
                    "decided_at": now_ts,
                })
                stats["new"] += 1
                continue

            # 임베딩 비교
            raw_text = f"{raw['title']} {raw.get('summary') or ''}"
            raw_vec = model.encode([raw_text], normalize_embeddings=True)[0]
            cand_texts = [c["title"] for c in candidates]
            cand_vecs = model.encode(cand_texts, normalize_embeddings=True)
            sims = cand_vecs @ raw_vec                         # 이미 정규화 → 코사인
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])
            best_cand = candidates[best_idx]

            # 엔티티 체크 (순서 고정 — 유사도 먼저 보지 않는다)
            cand_e = _build_cand_entities(best_cand)
            em = entities_match(raw_e, cand_e)

            if not em:
                decision = "new"
                new_c = _make_canonical(raw, signal, raw_e, now_ts)
                pending_canonicals.append(new_c)
                existing[(axis, company)].append(new_c)
                canonical_id = new_c["id"]
            elif best_sim >= threshold:
                decision = "merged"
                canonical_id = best_cand["id"]
                verification_updates.append((best_cand, signal, now_ts))
            else:
                decision = "new"
                new_c = _make_canonical(raw, signal, raw_e, now_ts)
                pending_canonicals.append(new_c)
                existing[(axis, company)].append(new_c)
                canonical_id = new_c["id"]

            merge_log_entries.append({
                "raw_id": raw["id"],
                "canonical_id": canonical_id,
                "similarity": round(best_sim, 4),
                "decision": decision,
                "entity_match": 1 if em else 0,
                "decided_at": now_ts,
            })
            stats[decision] += 1

        # 5. 배치 DB 기록
        for c in pending_canonicals:
            insert_canonical(conn, c)
        for entry in merge_log_entries:
            insert_merge_log(conn, entry)
        for (cand, sig, ts) in verification_updates:
            _apply_verification_update(conn, cand, sig, ts)
        conn.commit()

        print(
            f"[done]    new={stats['new']}  merged={stats['merged']}  "
            f"noise={stats['noise']}  "
            f"(pending_canonicals={len(pending_canonicals)})"
        )

    finally:
        conn.close()


def _apply_verification_update(conn, canonical: dict, signal: dict, ts: str) -> None:
    """merged: verification은 코드만 갱신 (LLM 덮어쓰기 금지)."""
    v = json.loads(canonical["verification"])
    new_date = signal.get("published_date") or ""
    if new_date and new_date > (v.get("published_date") or ""):
        v["published_date"] = new_date
        v["url"] = signal.get("url", v.get("url"))
    update_canonical(conn, canonical["id"], {
        "verification": json.dumps(v, ensure_ascii=False),
        "updated_at": ts,
    })


if __name__ == "__main__":
    run()
