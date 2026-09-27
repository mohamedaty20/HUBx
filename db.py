# db.py
# v12: Cloudflare D1 backend via REST API. Local SQLite fallback for dev.
#      Same public API as before — nothing else in the project changes.

import os
import json
import datetime
import logging
import threading
import sqlite3

import httpx

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

_db_lock = threading.RLock()


def _clean(v):
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    return v


# ------------------------------------------------------------------
# D1 credentials (all three must be present to use D1)
# ------------------------------------------------------------------
def _find_d1_creds():
    account_id = _clean(os.getenv("CLOUDFLARE_ACCOUNT_ID", ""))
    database_id = _clean(os.getenv("CLOUDFLARE_D1_DATABASE_ID", ""))
    api_token = _clean(os.getenv("CLOUDFLARE_API_TOKEN", ""))
    return account_id, database_id, api_token


# ------------------------------------------------------------------
# D1 HTTP connection (mimics the libsql connection surface we need)
# ------------------------------------------------------------------
class _D1Cursor:
    """Cursor-like object returned by _D1Connection.execute()."""

    def __init__(self, rows=None, lastrowid=None):
        self._rows = rows or []
        self._idx = 0
        self.lastrowid = lastrowid

    def fetchone(self):
        if self._idx < len(self._rows):
            row = self._rows[self._idx]
            self._idx += 1
            return row
        return None

    def fetchall(self):
        remaining = self._rows[self._idx:]
        self._idx = len(self._rows)
        return remaining


class _D1Connection:
    """
    Minimal synchronous wrapper around Cloudflare D1's /raw REST endpoint.
    Exposes .execute(sql, params), .executescript(sql), .commit().
    Rows are returned as tuples/arrays (same as libsql / sqlite3).
    """

    _BASE = "https://api.cloudflare.com/client/v4/accounts"

    def __init__(self, account_id, database_id, api_token):
        self._account_id = account_id
        self._database_id = database_id
        self._api_token = api_token
        self._url = (
            f"{self._BASE}/{account_id}/d1/database/{database_id}/raw"
        )
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(timeout=30.0)

    def _post(self, sql, params=None):
        payload = {"sql": sql}
        if params:
            payload["params"] = list(params)
        resp = self._client.post(
            self._url, json=payload, headers=self._headers
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("success"):
            errors = data.get("errors") or data
            raise RuntimeError(f"D1 query failed: {errors}")
        return data["result"][0]

    def execute(self, sql, params=()):
        result = self._post(sql, params)
        rows = (result.get("results") or {}).get("rows") or []
        last_id = (result.get("meta") or {}).get("last_row_id")
        return _D1Cursor(rows, lastrowid=last_id)

    def executescript(self, script):
        # Split on ';' and run each statement. The schema in init_db()
        # contains no semicolons inside string literals, so this is safe.
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                self.execute(stmt)

    def commit(self):
        # D1 auto-commits every statement.
        pass

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass


# ------------------------------------------------------------------
# Connection singleton
# ------------------------------------------------------------------
_conn = None
_db_mode = "not connected"
_db_error = ""


def _try_d1():
    account_id, database_id, api_token = _find_d1_creds()
    if not (account_id and database_id and api_token):
        raise ValueError("Cloudflare D1 credentials not set")
    conn = _D1Connection(account_id, database_id, api_token)
    # Smoke-test
    conn.execute("SELECT 1").fetchone()
    return conn


def get_conn():
    global _conn, _db_mode, _db_error
    if _conn is not None:
        return _conn
    try:
        _conn = _try_d1()
        _db_mode = "d1"
        _db_error = ""
        db_id = _find_d1_creds()[1]
        print(f"DB MODE = d1 ({db_id[:20]}...)")
        return _conn
    except Exception as e:
        _db_error = f"{type(e).__name__}: {e}"
        print(f"D1 failed: {_db_error}")
    # Fallback: local SQLite (dev only)
    _conn = sqlite3.connect("hubx.db", check_same_thread=False)
    _db_mode = "local"
    print("DB MODE = local SQLite")
    return _conn


def db_health():
    account_id, database_id, api_token = _find_d1_creds()
    return {
        "mode": _db_mode,
        "connection": database_id[:20] if _db_mode == "d1" else "hubx.db",
        "error": _db_error,
        "ok": _db_mode == "d1",
    }


def _exec(sql, params=()):
    """Thread-safe execute. Returns a cursor."""
    with _db_lock:
        conn = get_conn()
        return conn.execute(sql, params)


def _write(sql, params=()):
    """Thread-safe execute + commit."""
    with _db_lock:
        conn = get_conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def _ensure_column(conn, table, column, ddl):
    try:
        cols = [r[1] for r in
                conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            conn.commit()
            print(f"[db] added column {table}.{column}")
    except Exception as e:
        logger.warning("ensure_column %s.%s failed: %s", table, column, e)


def init_db():
    with _db_lock:
        conn = get_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT UNIQUE, category TEXT, content TEXT,
            refined_content TEXT, version INTEGER DEFAULT 1,
            confidence REAL DEFAULT 0.5, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE, category TEXT, content TEXT,
            refined_content TEXT, version INTEGER DEFAULT 1,
            confidence REAL DEFAULT 0.5, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS pending_topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT UNIQUE,
            category TEXT, source TEXT, parent_topic TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS pending_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE,
            category TEXT, source TEXT, parent_name TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS learning_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cycle INTEGER,
            topic_processed TEXT, items_added INTEGER DEFAULT 0,
            items_refined INTEGER DEFAULT 0, gemini_calls INTEGER DEFAULT 0,
            error TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS template_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cycle INTEGER,
            template_processed TEXT, items_added INTEGER DEFAULT 0,
            items_refined INTEGER DEFAULT 0, gemini_calls INTEGER DEFAULT 0,
            error TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS check_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT,
            file_type TEXT, original_text TEXT, issues_json TEXT,
            score REAL, summary TEXT, compliance TEXT, created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS gemini_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_gemini_usage_ts ON gemini_usage(ts);
        CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY, value TEXT
        );
        """)
        conn.commit()
        for col, ddl in [
            ("verified", "verified INTEGER DEFAULT 0"),
            ("flagged", "flagged INTEGER DEFAULT 0"),
            ("phase", "phase INTEGER DEFAULT 1"),
            ("phase_ts", "phase_ts TEXT"),
        ]:
            _ensure_column(conn, "knowledge", col, ddl)
            _ensure_column(conn, "templates", col, ddl)
        conn.commit()


# ==================================================================
# The rest of the file is IDENTICAL to your original db.py
# (app_state, gemini usage, knowledge, templates, pending queues,
#  runs, check_reports — all unchanged)
# ==================================================================

# ---------------- app_state ----------------
def get_app_state(key, default=""):
    try:
        row = _exec("SELECT value FROM app_state WHERE key=?",
                    (key,)).fetchone()
        return row[0] if row else default
    except Exception as e:
        logger.warning("get_app_state(%s) failed: %s", key, e)
        return default


def set_app_state(key, value):
    try:
        _write("""
            INSERT INTO app_state (key, value) VALUES (?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """, (key, str(value)))
    except Exception as e:
        logger.warning("set_app_state(%s) failed: %s", key, e)


# ---------------- gemini usage ----------------
def _utcnow_iso():
    return datetime.datetime.utcnow().isoformat()


def _iso_ago(seconds):
    return (datetime.datetime.utcnow()
            - datetime.timedelta(seconds=seconds)).isoformat()


def check_and_increment_gemini_usage(day_limit=600, hour_limit=40):
    try:
        day_count = _exec(
            "SELECT COUNT(*) FROM gemini_usage WHERE ts >= ?",
            (_iso_ago(86400),)).fetchone()[0]
        if day_count >= day_limit:
            return False
        hour_count = _exec(
            "SELECT COUNT(*) FROM gemini_usage WHERE ts >= ?",
            (_iso_ago(3600),)).fetchone()[0]
        if hour_count >= hour_limit:
            return False
        _write("INSERT INTO gemini_usage (ts) VALUES (?)",
               (_utcnow_iso(),))
        return True
    except Exception as e:
        logger.warning("gemini_usage check failed (allowing): %s", e)
        return True


def gemini_usage_stats(day_limit=600, hour_limit=40):
    try:
        d = _exec("SELECT COUNT(*) FROM gemini_usage WHERE ts >= ?",
                  (_iso_ago(86400),)).fetchone()[0]
        h = _exec("SELECT COUNT(*) FROM gemini_usage WHERE ts >= ?",
                  (_iso_ago(3600),)).fetchone()[0]
        return {"last_24h": d, "last_1h": h,
                "day_limit": day_limit, "hour_limit": hour_limit}
    except Exception:
        return {"last_24h": 0, "last_1h": 0,
                "day_limit": day_limit, "hour_limit": hour_limit}


def purge_old_gemini_usage(keep_days=None, keep_seconds=None):
    if keep_seconds is None:
        keep_seconds = (keep_days or 3) * 86400
    try:
        _write("DELETE FROM gemini_usage WHERE ts < ?",
               (_iso_ago(keep_seconds),))
    except Exception as e:
        logger.warning("purge failed: %s", e)


# ---------------- knowledge ----------------
def upsert_knowledge(topic, category, content, confidence=0.7):
    now = _utcnow_iso()
    row = _exec("SELECT id FROM knowledge WHERE topic = ?",
                (topic,)).fetchone()
    if row:
        _write("""
            UPDATE knowledge SET content=?, confidence=?,
                version=version+1, updated_at=? WHERE id=?
        """, (content, confidence, now, row[0]))
        return row[0]
    cur = _write("""
        INSERT INTO knowledge (topic, category, content, refined_content,
            version, confidence, phase, phase_ts, created_at, updated_at)
        VALUES (?,?,?,?,1,?,1,?,?,?)
    """, (topic, category, content, "", confidence, now, now, now))
    return cur.lastrowid


def get_knowledge_by_topic(topic):
    return _exec("SELECT * FROM knowledge WHERE topic=?", (topic,)).fetchone()


def get_knowledge_by_id(kid):
    return _exec("SELECT * FROM knowledge WHERE id=?", (kid,)).fetchone()


def verify_knowledge(kid):
    _write("UPDATE knowledge SET verified=1, flagged=0, "
           "confidence=1.0 WHERE id=?", (kid,))


def flag_knowledge(kid):
    _write("UPDATE knowledge SET flagged=1, verified=0 WHERE id=?", (kid,))


def clear_knowledge_flags(kid):
    _write("UPDATE knowledge SET flagged=0 WHERE id=?", (kid,))


def get_all_knowledge(category=None, limit=500):
    if category:
        return _exec("""
            SELECT id, topic, category, content, refined_content, version,
                   confidence, updated_at
            FROM knowledge WHERE category=?
            ORDER BY updated_at DESC LIMIT ?
        """, (category, limit)).fetchall()
    return _exec("""
        SELECT id, topic, category, content, refined_content, version,
               confidence, updated_at
        FROM knowledge ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()


def search_knowledge(query, limit=8):
    like = f"%{query}%"
    return _exec("""
        SELECT id, topic, category, content, refined_content, version
        FROM knowledge
        WHERE topic LIKE ? OR content LIKE ? OR refined_content LIKE ?
        ORDER BY updated_at DESC LIMIT ?
    """, (like, like, like, limit)).fetchall()


def knowledge_stats():
    total = _exec("SELECT COUNT(*) FROM knowledge").fetchone()[0]
    refined = _exec("SELECT COUNT(*) FROM knowledge WHERE version > 1"
                    ).fetchone()[0]
    pending = _exec("SELECT COUNT(*) FROM pending_topics").fetchone()[0]
    verified = _exec(
        "SELECT COUNT(*) FROM knowledge WHERE COALESCE(verified,0)=1"
    ).fetchone()[0]
    flagged = _exec(
        "SELECT COUNT(*) FROM knowledge WHERE COALESCE(flagged,0)=1"
    ).fetchone()[0]
    return {"total": total, "refined": refined, "pending": pending,
            "verified": verified, "flagged": flagged}


def category_counts():
    return _exec("""
        SELECT category, COUNT(*) FROM knowledge
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category ORDER BY COUNT(*) DESC
    """).fetchall()


def confidence_bins():
    rows = _exec(
        "SELECT confidence FROM knowledge WHERE confidence IS NOT NULL"
    ).fetchall()
    bins = {f"{i/10:.1f}": 0 for i in range(0, 11)}
    for r in rows:
        c = float(r[0] or 0.0)
        key = f"{min(int(c*10), 10)/10:.1f}"
        bins[key] = bins.get(key, 0) + 1
    return sorted(bins.items())


def version_counts():
    return _exec("""
        SELECT version, COUNT(*) FROM knowledge
        GROUP BY version ORDER BY version
    """).fetchall()


def runs_per_cycle(limit=40):
    rows = _exec("""
        SELECT cycle, items_added, items_refined
        FROM learning_runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
    return rows[::-1]


# ---------------- templates ----------------
def upsert_template(name, category, content, confidence=0.7):
    now = _utcnow_iso()
    row = _exec("SELECT id FROM templates WHERE name = ?",
                (name,)).fetchone()
    if row:
        _write("""
            UPDATE templates SET content=?, confidence=?,
                version=version+1, updated_at=? WHERE id=?
        """, (content, confidence, now, row[0]))
        return row[0]
    cur = _write("""
        INSERT INTO templates (name, category, content, refined_content,
            version, confidence, phase, phase_ts, created_at, updated_at)
        VALUES (?,?,?,?,1,?,1,?,?,?)
    """, (name, category, content, "", confidence, now, now, now))
    return cur.lastrowid


def get_template_by_name(name):
    return _exec("SELECT * FROM templates WHERE name=?", (name,)).fetchone()


def get_template_by_id(tid):
    return _exec("SELECT * FROM templates WHERE id=?", (tid,)).fetchone()


def verify_template(tid):
    _write("UPDATE templates SET verified=1, flagged=0, "
           "confidence=1.0 WHERE id=?", (tid,))


def flag_template(tid):
    _write("UPDATE templates SET flagged=1, verified=0 WHERE id=?", (tid,))


def get_all_templates(category=None, limit=200):
    if category:
        return _exec("""
            SELECT id, name, category, content, refined_content, version,
                   confidence, updated_at
            FROM templates WHERE category=?
            ORDER BY updated_at DESC LIMIT ?
        """, (category, limit)).fetchall()
    return _exec("""
        SELECT id, name, category, content, refined_content, version,
               confidence, updated_at
        FROM templates ORDER BY updated_at DESC LIMIT ?
    """, (limit,)).fetchall()


def template_category_counts():
    return _exec("""
        SELECT category, COUNT(*) FROM templates
        WHERE category IS NOT NULL AND category != ''
        GROUP BY category ORDER BY COUNT(*) DESC
    """).fetchall()


def template_stats():
    total = _exec("SELECT COUNT(*) FROM templates").fetchone()[0]
    refined = _exec("SELECT COUNT(*) FROM templates WHERE version > 1"
                    ).fetchone()[0]
    pending = _exec("SELECT COUNT(*) FROM pending_templates").fetchone()[0]
    verified = _exec(
        "SELECT COUNT(*) FROM templates WHERE COALESCE(verified,0)=1"
    ).fetchone()[0]
    flagged = _exec(
        "SELECT COUNT(*) FROM templates WHERE COALESCE(flagged,0)=1"
    ).fetchone()[0]
    return {"total": total, "refined": refined, "pending": pending,
            "verified": verified, "flagged": flagged}


# ---------------- pending queues ----------------
def add_pending_topic(topic, category, source="ai", parent_topic=""):
    topic = (topic or "").strip()
    category = (category or "").strip() or "general"
    if not topic or len(topic) < 6:
        return False
    ex = _exec("SELECT 1 FROM knowledge WHERE topic = ?",
               (topic,)).fetchone()
    if ex:
        return False
    try:
        _write("""
            INSERT OR IGNORE INTO pending_topics
            (topic, category, source, parent_topic, created_at)
            VALUES (?,?,?,?,?)
        """, (topic, category, source, parent_topic, _utcnow_iso()))
        return True
    except Exception:
        return False


def pop_pending_topic():
    row = _exec("""
        SELECT id, topic, category FROM pending_topics
        ORDER BY id ASC LIMIT 1
    """).fetchone()
    if not row:
        return None
    _write("DELETE FROM pending_topics WHERE id = ?", (row[0],))
    return (row[1], row[2])


def pending_count():
    return _exec("SELECT COUNT(*) FROM pending_topics").fetchone()[0]


def add_pending_template(name, category, source="ai", parent_name=""):
    name = (name or "").strip()
    category = (category or "").strip() or "administrative"
    if not name or len(name) < 6:
        return False
    ex = _exec("SELECT 1 FROM templates WHERE name = ?",
               (name,)).fetchone()
    if ex:
        return False
    try:
        _write("""
            INSERT OR IGNORE INTO pending_templates
            (name, category, source, parent_name, created_at)
            VALUES (?,?,?,?,?)
        """, (name, category, source, parent_name, _utcnow_iso()))
        return True
    except Exception:
        return False


def pop_pending_template():
    row = _exec("""
        SELECT id, name, category FROM pending_templates
        ORDER BY id ASC LIMIT 1
    """).fetchone()
    if not row:
        return None
    _write("DELETE FROM pending_templates WHERE id = ?", (row[0],))
    return (row[1], row[2])


def pending_template_count():
    return _exec("SELECT COUNT(*) FROM pending_templates").fetchone()[0]


# ---------------- runs ----------------
def log_learning_run(cycle, topic, added, refined, calls, error=""):
    _write("""
        INSERT INTO learning_runs (cycle, topic_processed, items_added,
            items_refined, gemini_calls, error, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (cycle, topic, added, refined, calls, error[:500], _utcnow_iso()))


def recent_learning_runs(limit=20):
    return _exec("""
        SELECT cycle, topic_processed, items_added, items_refined,
               gemini_calls, error, created_at
        FROM learning_runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()


def log_template_run(cycle, name, added, refined, calls, error=""):
    _write("""
        INSERT INTO template_runs (cycle, template_processed, items_added,
            items_refined, gemini_calls, error, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (cycle, name, added, refined, calls, error[:500], _utcnow_iso()))


def recent_template_runs(limit=20):
    return _exec("""
        SELECT cycle, template_processed, items_added, items_refined,
               gemini_calls, error, created_at
        FROM template_runs ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()


def save_check_report(filename, file_type, original_text, issues,
                      score, summary, compliance=""):
    cur = _write("""
        INSERT INTO check_reports (filename, file_type, original_text,
            issues_json, score, summary, compliance, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (filename, file_type, original_text, json.dumps(issues),
          score, summary, compliance, _utcnow_iso()))
    return cur.lastrowid


def recent_check_reports(limit=50):
    return _exec("""
        SELECT id, filename, file_type, score, summary, created_at
        FROM check_reports ORDER BY id DESC LIMIT ?
    """, (limit,)).fetchall()
