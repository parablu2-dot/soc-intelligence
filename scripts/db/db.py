"""SQLite helper — get_conn, init_db, CRUD wrappers."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "soc.db"
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_conn()
    try:
        conn.executescript(schema)   # executescript은 내부적으로 COMMIT 포함
    finally:
        conn.close()                 # WAL 파일 잠금 해제 (Windows 호환)


# ── raw_documents ──────────────────────────────────────────────────────────────

def insert_raw(conn: sqlite3.Connection, doc: dict) -> None:
    """INSERT OR IGNORE — raw_documents는 append-only."""
    conn.execute(
        "INSERT OR IGNORE INTO raw_documents "
        "(id, crawled_at, source, axis, company, title, summary, url, raw_json) "
        "VALUES (:id, :crawled_at, :source, :axis, :company, :title, :summary, :url, :raw_json)",
        doc,
    )


def get_unprocessed_raws(conn: sqlite3.Connection) -> list:
    """merge_log에 raw_id가 없는 raw_documents 반환."""
    return conn.execute(
        "SELECT * FROM raw_documents "
        "WHERE id NOT IN (SELECT raw_id FROM merge_log)"
    ).fetchall()


# ── canonical_nodes ────────────────────────────────────────────────────────────

def insert_canonical(conn: sqlite3.Connection, node: dict) -> None:
    """INSERT OR IGNORE — 동일 id가 있으면 건너뜀."""
    conn.execute(
        "INSERT OR IGNORE INTO canonical_nodes "
        "(id, axis, company, entity_keys, title, verification, inference, created_at, updated_at) "
        "VALUES (:id, :axis, :company, :entity_keys, :title, :verification, :inference, :created_at, :updated_at)",
        node,
    )


def update_canonical(conn: sqlite3.Connection, node_id: str, updates: dict) -> None:
    """지정 필드만 갱신. updates에 updated_at 반드시 포함."""
    params = dict(updates)
    sets = ", ".join(f"{k} = :{k}" for k in params)
    params["_node_id"] = node_id
    conn.execute(f"UPDATE canonical_nodes SET {sets} WHERE id = :_node_id", params)


def get_all_canonical(conn: sqlite3.Connection) -> list:
    return conn.execute("SELECT * FROM canonical_nodes").fetchall()


def get_canonical_by_axis_company(conn: sqlite3.Connection, axis: str, company: str) -> list:
    return conn.execute(
        "SELECT * FROM canonical_nodes WHERE axis = ? AND company = ?",
        (axis, company),
    ).fetchall()


# ── merge_log ──────────────────────────────────────────────────────────────────

def insert_merge_log(conn: sqlite3.Connection, entry: dict) -> None:
    """INSERT only — merge_log는 append-only."""
    conn.execute(
        "INSERT INTO merge_log "
        "(raw_id, canonical_id, similarity, decision, entity_match, decided_at) "
        "VALUES (:raw_id, :canonical_id, :similarity, :decision, :entity_match, :decided_at)",
        entry,
    )
