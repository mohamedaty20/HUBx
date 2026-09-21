# db.py
# Turso with local fallback. Version replacement + templates + search.

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


def _find_url():
    for k, v in os.environ.items():
        v = _clean(v)
        if v.startswith("libsql://"):
            return k, v
    return None, ""


def _find_token():
    for k, v in os.environ.items():
        v = _clean(v)
        if v.startswith("eyJ") and len(v) > 100:
            return k, v
    return None, ""


_URL_KEY, _TURSO_URL_RAW = _find_url()
_TOKEN_KEY, _TURSO_TOKEN_RAW = _find_token()

_conn = None
_db_mode = "not connected"
_db_error = ""


def _try_turso():
    if not _TURSO_URL_RAW.startswith("libsql://"):
        raise ValueError("no libsql:// URL found")
    if not _TURSO_TOKEN_RAW:
        raise ValueError("no Turso token found")
    conn = libsql.connect(_TURSO_URL_RAW, auth_token=_TURSO_TOKEN_RAW)
    conn.execute("SELECT 1").fetchone()
    return conn


def get_conn():
    global _conn, _db_mode, _db_error
    if _conn is not None:
        return _conn
    try:
        _conn = _try_turso()
        _db_mode = "turso"
        _db_error = ""
        print(f"DB MODE = turso ({_TURSO_URL_RAW[:40]}...)")
        return _conn
    except Exception as e:
        _db_error = f"{type(e).__name__}: {e}"
        print(f"Turso failed: {_db_error}")
    _conn = libsql.connect("hubx.db")
    _db_mode = "local"
    print("DB MODE = local SQLite")
    return _conn


def db_health():
    return {
        "mode": _db_mode,
        "connection": _TURSO_URL_RAW[:40] if _db_mode == "turso"
                      else "hubx.db",
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
    CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        content TEXT,
        refined_content TEXT,
        version INTEGER DEFAULT 1,
        confidence REAL DEFAULT 0.5,
        created_at TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS pending_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT UNIQUE,
        category TEXT,
        source TEXT,
        parent_topic TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS pending_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        category TEXT,
        source TEXT,
        parent_name TEXT,
        created_at TEXT
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
    CREATE TABLE IF NOT EXISTS template_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cycle INTEGER,
        template_processed TEXT,
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
        compliance TEXT,
        created_at TEXT
    );
    """)
    conn.commit()


# ---------------- knowledge ----------------

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


def replace_knowledge_with_refined(knowledge_id, refined):
    conn = get_conn()
    row = conn.execute(
        "SELECT topic, category, version FROM knowledge WHERE id = ?",
        (knowledge_id,)).fetchone()
    if not row:
        return
    topic, category, version = row
    now = datetime.datetime.utcnow().isoformat()
    conn.execute("DELETE FROM knowledge WHERE id = ?", (knowledge_id,))
    conn.execute("""
        INSERT INTO knowledge (topic, category, content, refined_content,
            version, confidence, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (topic, category, refined, refined, version + 1, 0.85, now, now))
    conn.commit()


def oldest_knowledge_for_refinement(limit=1):
    conn = get_conn()
    return conn.execute("""
        SELECT id, topic, category, content, refined_content, version
        FROM knowledge ORDER BY updated_at ASC LIMIT ?
    """, (limit,)).fetchall()


def get_all_knowledge(category=None, limit=500):
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


def search_knowledge(query, limit=8):
    conn = get_conn()
    like = f"%{query}%"
    return conn.execute("""
        SELECT id, topic, category, content, refined_content, version
        FROM knowledge
        WHERE topic LIKE ? OR content LIKE ? OR refined_content LIKE ?
        ORDER BY updated_at DESC LIMIT ?
    """, (like, like, like, limit)).fetchall()


def knowledge_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    refined = conn.execute(
        "SELECT COUNT(*) FROM knowledge WHERE refined_content != ''"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM pending_topics").fetchone()[0]
    return {"total": total, "refined": refined, "pending": pending}


def category_counts():
    conn = get_conn()
    return conn.execute("""
        SELECT category, COUNT(*) FROM knowledge
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category ORDER BY COUNT(*) DESC
    """).fetchall()


def confidence_bins():
    conn = get_conn()
    rows = conn.execute(
        "SELECT confidence FROM knowledge WHERE confidence IS NOT NULL"
    ).fetchall()
    bins = {f"{i/10:.1f}": 0 for i in range(0, 11)}
    for r in rows:
        c = float(r[0] or 0.0)
        key = f"{min(int(c*10), 10)/10:.1f}"
        bins[key] = bins.get(key, 0) + 1
    return sorted(bins.items())


def version_counts():
    conn = get_conn()
    return conn.execute("""
        SELECT version, COUNT(*) FROM knowledge
        GROUP BY version ORDER BY version
    """).fetchall()


def runs_per_cycle(limit=40):
    conn = get_conn()
    return conn.execute("""
        SELECT cycle, items_added, items_refined
        FROM learning_runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()[::-1]


# ---------------- templates ----------------

def upsert_template(name, category, content, confidence=0.5):
    conn = get_conn()
    now = datetime.datetime.utcnow().isoformat()
    row = conn.execute(
        "SELECT id, version FROM templates WHERE name = ?", (name,)
    ).fetchone()
    if row:
        conn.execute("""
            UPDATE templates SET content=?, confidence=?,
                version=version+1, updated_at=? WHERE id=?
        """, (content, confidence, now, row[0]))
        conn.commit()
        return row[0]
    cur = conn.execute("""
        INSERT INTO templates (name, category, content, refined_content,
            version, confidence, created_at, updated_at)
        VALUES (?,?,?,?,1,?,?,?)
    """, (name, category, content, "", confidence, now, now))
    conn.commit()
    return cur.lastrowid


def replace_template_with_refined(template_id, refined):
    conn = get_conn()
    row = conn.execute(
        "SELECT name, category, version FROM templates WHERE id = ?",
        (template_id,)).fetchone()
    if not row:
        return
    name, category, version = row
    now = datetime.datetime.utcnow().isoformat()
    conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))
    conn.execute("""
        INSERT INTO templates (name, category, content, refined_content,
            version, confidence, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (name, category, refined, refined, version + 1, 0.85, now, now))
    conn.commit()


def oldest_template_for_refinement(limit=1):
    conn = get_conn()
    return conn.execute("""
        SELECT id, name, category, content, refined_content, version
        FROM templates ORDER BY updated_at ASC LIMIT ?
    """, (limit,)).fetchall()


def get_all_templates(category=None, limit=200):
    conn = get_conn()
    if category:
        return conn.execute("""
            SELECT id, name, category, content, refined_content, version,
                   confidence, updated_at
            FROM templates WHERE category=?
            ORDER BY updated_at DESC LIMIT ?
        """, (category, limit)).fetchall()
    return conn.execute("""
        SELECT id, name, category, content, refined_content, version,
               confidence, updated_at
        FROM templates ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()


def get_template_by_id(template_id):
    conn = get_conn()
    return conn.execute(
        "SELECT * FROM templates WHERE id=?", (template_id,)).fetchone()


def template_category_counts():
    conn = get_conn()
    return conn.execute("""
        SELECT category, COUNT(*) FROM templates
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category ORDER BY COUNT(*) DESC
    """).fetchall()


def template_stats():
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0]
    refined = conn.execute(
        "SELECT COUNT(*) FROM templates WHERE refined_content != ''"
    ).fetchone()[0]
    pending = conn.execute(
        "SELECT COUNT(*) FROM pending_templates").fetchone()[0]
    return {"total": total, "refined": refined, "pending": pending}


# ---------------- pending_topics ----------------

def add_pending_topic(topic, category, source="ai", parent_topic=""):
    conn = get_conn()
    topic = (topic or "").strip()
    category = (category or "").strip() or "general"
    if not topic or len(topic) < 6:
        return False
    ex = conn.execute(
        "SELECT 1 FROM knowledge WHERE topic = ?", (topic,)).fetchone()
    if ex:
        return False
    try:
        conn.execute("""
            INSERT OR IGNORE INTO pending_topics
            (topic, category, source, parent_topic, created_at)
            VALUES (?,?,?,?,?)
        """, (topic, category, source, parent_topic,
              datetime.datetime.utcnow().isoformat()))
        conn.commit()
        return True
    except Exception:
        return False


def pop_pending_topic():
    conn = get_conn()
    row = conn.execute("""
        SELECT id, topic, category FROM pending_topics
        ORDER BY id ASC LIMIT 1
    """).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM pending_topics WHERE id = ?", (row[0],))
    conn.commit()
    return (row[1], row[2])


def pending_count():
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) FROM pending_topics").fetchone()[0]


# ---------------- pending_templates ----------------

def add_pending_template(name, category, source="ai", parent_name=""):
    conn = get_conn()
    name = (name or "").strip()
    category = (category or "").strip() or "administrative"
    if not name or len(name) < 6:
        return False
    ex = conn.execute(
        "SELECT 1 FROM templates WHERE name = ?", (name,)).fetchone()
    if ex:
        return False
    try:
        conn.execute("""
            INSERT OR IGNORE INTO pending_templates
            (name, category, source, parent_name, created_at)
            VALUES (?,?,?,?,?)
        """, (name, category, source, parent_name,
              datetime.datetime.utcnow().isoformat()))
        conn.commit()
        return True
    except Exception:
        return False


def pop_pending_template():
    conn = get_conn()
    row = conn.execute("""
        SELECT id, name, category FROM pending_templates
        ORDER BY id ASC LIMIT 1
    """).fetchone()
    if not row:
        return None
    conn.execute("DELETE FROM pending_templates WHERE id = ?", (row[0],))
    conn.commit()
    return (row[1], row[2])


def pending_template_count():
    conn = get_conn()
    return conn.execute(
        "SELECT COUNT(*) FROM pending_templates").fetchone()[0]


# ---------------- runs ----------------

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


def log_template_run(cycle, name, added, refined, calls, error=""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO template_runs (cycle, template_processed, items_added,
            items_refined, gemini_calls, error, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (cycle, name, added, refined, calls, error[:500],
          datetime.datetime.utcnow().isoformat()))
    conn.commit()


def recent_template_runs(limit=20):
    conn = get_conn()
    return conn.execute("""
        SELECT cycle, template_processed, items_added, items_refined,
               gemini_calls, error, created_at
        FROM template_runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()


# ---------------- check_reports ----------------

def save_check_report(filename, file_type, original_text, issues,
                      score, summary, compliance=""):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO check_reports (filename, file_type, original_text,
            issues_json, score, summary, compliance, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (filename, file_type, original_text, json.dumps(issues), score,
          summary, compliance, datetime.datetime.utcnow().isoformat()))
    conn.commit()
    return cur.lastrowid


def recent_check_reports(limit=50):
    conn = get_conn()
    return conn.execute("""
        SELECT id, filename, file_type, score, summary, created_at
        FROM check_reports ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
