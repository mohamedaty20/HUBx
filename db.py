# db.py
# Turso schema + CRUD. Refuses to fall back to a local file on Render.

import os
import json
import datetime
import logging
from typing import Any

import libsql

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _clean(v: str) -> str:
    """Strip whitespace AND accidental surrounding quotes."""
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v


TURSO_URL = _clean(os.getenv("TURSO_DATABASE_URL", ""))
TURSO_TOKEN = _clean(os.getenv("TURSO_AUTH_TOKEN", ""))
ON_RENDER = bool(os.getenv("RENDER"))

# --- boot-time diagnostics: visible in Render logs ---
print("=== HUBx env check ===")
print(f"RENDER              = {os.getenv('RENDER')!r}")
print(f"TURSO_DATABASE_URL  = len={len(TURSO_URL)} startswith_libsql="
      f"{TURSO_URL.startswith('libsql://')} head={TURSO_URL[:30]!r}")
print(f"TURSO_AUTH_TOKEN    = len={len(TURSO_TOKEN)} head={TURSO_TOKEN[:8]!r}")
print(f"GEMINI_API_KEY      = len={len(os.getenv('GEMINI_API_KEY',''))}")
print(f"GEMINI_MODEL        = {os.getenv('GEMINI_MODEL')!r}")
print("=====================")

_conn = None
_conn_info = "not connected"


def get_conn():
    global _conn, _conn_info
    if _conn is not None:
        return _conn

    if TURSO_URL.startswith("libsql://"):
        _conn = libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
        _conn_info = f"turso: {TURSO_URL[:40]}..."
        logger.info("Connected to Turso: %s", TURSO_URL[:40])
    elif TURSO_URL.startswith("file:"):
        if ON_RENDER:
            raise RuntimeError(
                "TURSO_DATABASE_URL is a local file but you are on Render. "
                "Set it to your libsql:// URL in the Render Environment tab."
            )
        _conn = libsql.connect(TURSO_URL.replace("file:", ""))
        _conn_info = f"local file: {TURSO_URL}"
    else:
        if ON_RENDER:
            raise RuntimeError(
                "TURSO_DATABASE_URL is not set or is malformed. It must "
                "start with libsql://. Current value length="
                f"{len(TURSO_URL)}. Add it in the Render Environment tab."
            )
        _conn = libsql.connect("hubx.db")
        _conn_info = "local file: hubx.db (dev only)"
    return _conn


def db_health() -> dict:
    info = {"connection": _conn_info, "ok": False, "error": ""}
    try:
        conn = get_conn()
        info["knowledge"] = conn.execute(
            "SELECT COUNT(*) FROM knowledge").fetchone()[0]
        info["runs"] = conn.execute(
            "SELECT COUNT(*) FROM learning_runs").fetchone()[0]
        info["checks"] = conn.execute(
            "SELECT COUNT(*) FROM check_reports").fetchone()[0]
        info["ok"] = True
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
    return info


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS knowledge (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE,
        category TEXT,
        content TEXT,
        refined_content TEXT,
        version INTEGER DEFAULT 1,
        confidence REAL DEFAULT 0.5,
        created_at TEXT,
        updated_at TEXT
    );

    CREATE TABLE IF NOT EXISTS learning_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle INTEGER,
        topic_processed TEXT,
        items_added INTEGER DEFAULT 0,
        items_refined INTEGER DEFAULT 0,
        gemini_calls INTEGER DEFAULT 0,
        error TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS check_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT,
        file_type TEXT,
        original_text TEXT,
        issues_json TEXT,
        score REAL,
        summary TEXT,
        created_at TEXT
    );
    """)
    conn.commit()


def upsert_knowledge(topic: str, category: str, content: str,
                     confidence: float = 0.5) -> int:
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    row = conn.execute(
        "SELECT id, version FROM knowledge WHERE topic = ?", (topic,)
    ).fetchone()
    if row:
        conn.execute("""
            UPDATE knowledge
            SET content = ?, confidence = ?, version = version + 1,
                updated_at = ?
            WHERE id = ?
        """, (content, confidence, now, row[0]))
        conn.commit()
        return row[0]
    cur = conn.execute("""
        INSERT INTO knowledge (topic, category, content, refined_content,
            version, confidence, created_at, updated_at)
        VALUES (?,?,?,?,1,?,?,?)
    """, (topic, category, content, "", confidence, now, now))
    conn.commit()
    return cur.lastrowid


def set_refined(knowledge_id: int, refined: str, confidence: float = 0.7):
    conn = get_conn()
    conn.execute("""
        UPDATE knowledge
        SET refined_content = ?, confidence = ?, updated_at = ?
        WHERE id = ?
    """, (refined, confidence,
          datetime.datetime.utcnow().isoformat(), knowledge_id))
    conn.commit()


def oldest_knowledge_for_refinement(limit: int = 1):
    conn = get_conn()
    return conn.execute("""
        SELECT id, topic, category, content, refined_content, version
        FROM knowledge
        ORDER BY updated_at ASC
        LIMIT ?
    """, (limit,)).fetchall()


def get_all_knowledge(category: str | None = None, limit: int = 200):
    conn = get_conn()
    if category:
        return conn.execute("""
            SELECT id, topic, category, content, refined_content, version,
                   confidence, updated_at
            FROM knowledge WHERE category = ?
            ORDER BY updated_at DESC LIMIT ?
        """, (category, limit)).fetchall()
    return conn.execute("""
        SELECT id, topic, category, content, refined_content, version,
               confidence, updated_at
        FROM knowledge
        ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()


def get_knowledge_by_id(knowledge_id: int):
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM knowledge WHERE id = ?", (knowledge_id,)
    ).fetchone()


def knowledge_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    refined = conn.execute(
        "SELECT COUNT(*) FROM knowledge WHERE refined_content != ''"
    ).fetchone()[0]
    return {"total": total, "refined": refined}


def log_learning_run(cycle: int, topic: str, added: int, refined: int,
                     calls: int, error: str = ""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO learning_runs (cycle, topic_processed, items_added,
            items_refined, gemini_calls, error, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (cycle, topic, added, refined, calls, error[:500],
          datetime.datetime.utcnow().isoformat()))
    conn.commit()


def recent_learning_runs(limit: int = 20):
    conn = get_conn()
    return conn.execute("""
        SELECT cycle, topic_processed, items_added, items_refined,
               gemini_calls, error, created_at
        FROM learning_runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()


def save_check_report(filename: str, file_type: str, original_text: str,
                      issues: list, score: float, summary: str) -> int:
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO check_reports (filename, file_type, original_text,
            issues_json, score, summary, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (filename, file_type, original_text,
          json.dumps(issues), score, summary,
          datetime.datetime.utcnow().isoformat()))
    conn.commit()
    return cur.lastrowid


def recent_check_reports(limit: int = 50):
    conn = get_conn()
    return conn.execute("""
        SELECT id, filename, file_type, score, summary, created_at
        FROM check_reports ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
