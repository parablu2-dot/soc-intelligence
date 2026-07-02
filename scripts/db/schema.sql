-- v3 Dedup·Lineage 파이프라인 SQLite 스키마
-- raw_documents, merge_log: append-only (UPDATE/DELETE 금지)
-- canonical_nodes: dedup 후 대표 노드 (갱신 허용)

CREATE TABLE IF NOT EXISTS raw_documents (
    id          TEXT PRIMARY KEY,       -- sha256(url)[:24]
    crawled_at  TEXT NOT NULL,          -- ISO 8601 datetime
    source      TEXT NOT NULL,
    axis        TEXT NOT NULL,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT,
    url         TEXT NOT NULL,
    raw_json    TEXT NOT NULL           -- 원본 RefinedSignal JSON (불변)
);

CREATE TABLE IF NOT EXISTS canonical_nodes (
    id           TEXT PRIMARY KEY,      -- 최초 raw_id (sha256(url)[:24])
    axis         TEXT NOT NULL,
    company      TEXT NOT NULL,
    entity_keys  TEXT NOT NULL,         -- JSON array: 공정 노드 + 제품 엔티티
    title        TEXT NOT NULL,
    verification TEXT NOT NULL,         -- JSON: source-verified 필드만 (LLM 덮어쓰기 금지)
    inference    TEXT NOT NULL,         -- JSON: LLM-refined 필드 (tags, summary)
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS merge_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_id       TEXT    NOT NULL,      -- raw_documents.id 참조
    canonical_id TEXT,                  -- NULL 허용: noise 판정 시
    similarity   REAL,                  -- 코사인 유사도 (entity mismatch → NULL)
    decision     TEXT    NOT NULL,      -- 'new' | 'merged' | 'noise'
    entity_match INTEGER NOT NULL,      -- 0=불일치, 1=일치 (bool)
    decided_at   TEXT    NOT NULL       -- ISO 8601 datetime
);

CREATE INDEX IF NOT EXISTS idx_merge_log_raw_id  ON merge_log(raw_id);
CREATE INDEX IF NOT EXISTS idx_merge_log_decision ON merge_log(decision);
CREATE INDEX IF NOT EXISTS idx_canonical_axis_co  ON canonical_nodes(axis, company);
