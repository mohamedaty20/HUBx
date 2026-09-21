# db.py
# Turso with automatic local-SQLite fallback so the app never brick-walls.
# If TURSO_DATABASE_URL is valid we use Turso (persistent).
# If not, we use a local file (works, but data is lost on Render redeploy).

import os
import json
import datetime
import logging

import libsql

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _clean(v):
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v


_TURSO_URL_RAW = _clean(os.getenv("TURSO_DATABASE_URL", ""))
_TURSO_TOKEN_RAW = _clean(os.getenv("TURSO_AUTH_TOKEN", ""))

_conn = None
_db_mode = "not connected"
_db_error = ""


def _try_turso():
    """Return a connection or raise. Also validates the token works."""
    if not _TURSO_URL_RAW.startswith("libsql://"):
        raise ValueError("TURSO_DATABASE_URL missing or not libsql://")
    if not _TURSO_TOKEN_RAW:
        raise ValueError("TURSO_AUTH_TOKEN missing")
    conn = libsql.connect(_TURSO_URL_RAW, auth_token=_TURSO_TOKEN_RAW)
    # Force a real round-trip so a bad token fails here, not later.
    conn.execute("SELECT 1").fetchone()
    return conn


def get_conn():
    global _conn, _db_mode, _db_error
    if _conn is not None:
        return _conn

    print(f"=== HUBx DB init ===")
    print(f"TURSO url len={len(_TURSO_URL_RAW)} "
          f"starts_libsql={_TURSO_URL_RAW.startswith('libsql://')}")
    print(f"TURSO token len={len(_TURSO_TOKEN_RAW)}")

    # 1) Try Turso
    try:
        _conn = _try_turso()
        _db_mode = "turso"
        _db_error = ""
        print(f"DB MODE = turso ({_TURSO_URL_RAW[:40]}...)")
        print("====================")
        return _conn
    except Exception as e:
        _db_error = f"{type(e).__name__}: {e}"
        print(f"Turso failed: {_db_error}")
        print("Falling back to local SQLite (data lost on redeploy).")

    # 2) Fallback to local file
    _conn = libsql.connect("hubx.db")
    _db_mode = "local"
    print(f"DB MODE = local SQLite (hubx.db in container)")
    print("====================")
    return _conn


def db_health():
    return {
        "mode": _db_mode,
        "connection": _TURSO_URL_RAW[:40] if _db_mode == "turso" else "hubx.db",
        "error": _db_error,
        "ok": _db_mode == "turso",
    }


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


def upsert_knowledge(topic, category, content, confidence=0.5):
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    row = conn.execute(
        "SELECT id, version FROM knowledge WHERE topic = ?", (topic,)
    ).fetchone()
    if row:
        conn.execute("""
            UPDATE knowledge SET content=?, confidence=?,
                version=version+1, updated_at=? WHERE id=?
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


def set_refined(knowledge_id, refined, confidence=0.7):
    conn = get_conn()
    conn.execute("""
        UPDATE knowledge SET refined_content=?, confidence=?, updated_at=?
        WHERE id=?
    """, (refined, confidence,
          datetime.datetime.utcnow().isoformat(), knowledge_id))
    conn.commit()


def oldest_knowledge_for_refinement(limit=1):
    conn = get_conn()
    return conn.execute("""
        SELECT id, topic, category, content, refined_content, version
        FROM knowledge ORDER BY updated_at ASC LIMIT ?
    """, (limit,)).fetchall()


def get_all_knowledge(category=None, limit=200):
    conn = get_conn()
    if category:
        return conn.execute("""
            SELECT id, topic, category, content, refined_content, version,
                   confidence, updated_at
            FROM knowledge WHERE category=?
            ORDER BY updated_at DESC LIMIT ?
        """, (category, limit)).fetchall()
    return conn.execute("""
        SELECT id, topic, category, content, refined_content, version,
               confidence, updated_at
        FROM knowledge ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()


def get_knowledge_by_id(knowledge_id):
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM knowledge WHERE id=?", (knowledge_id,)).fetchone()


def knowledge_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    refined = conn.execute(
        "SELECT COUNT(*) FROM knowledge WHERE refined_content != ''"
    ).fetchone()[0]
    return {"total": total, "refined": refined}


def log_learning_run(cycle, topic, added, refined, calls, error=""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO learning_runs (cycle, topic_processed, items_added,
            items_refined, gemini_calls, error, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (cycle, topic, added, refined, calls, error[:500],
          datetime.datetime.utcnow().isoformat()))
    conn.commit()


def recent_learning_runs(limit=20):
    conn = get_conn()
    return conn.execute("""
        SELECT cycle, topic_processed, items_added, items_refined,
               gemini_calls, error, created_at
        FROM learning_runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()


def save_check_report(filename, file_type, original_text, issues,
                      score, summary):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO check_reports (filename, file_type, original_text,
            issues_json, score, summary, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (filename, file_type, original_text, json.dumps(issues), score,
          summary, datetime.datetime.utcnow().isoformat()))
    conn.commit()
    return cur.lastrowid


def recent_check_reports(limit=50):
    conn = get_conn()
    return conn.execute("""
        SELECT id, filename, file_type, score, summary, created_at
        FROM check_reports ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
