# db.py
# Turso / SQLite schema + CRUD helpers.
# Personal data stored only if verbatim in the public posting.

import os
import json
import datetime
from typing import Any

import libsql

TURSO_URL = os.getenv("TURSO_DATABASE_URL", "file:hubx.db")
TURSO_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "")

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        if TURSO_URL.startswith("file:"):
            _conn = libsql.connect(TURSO_URL.replace("file:", ""))
        else:
            _conn = libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
    return _conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        company TEXT,
        location TEXT,
        posted_date TEXT,
        url TEXT,
        description_full TEXT,
        recruiter_name TEXT,
        recruiter_title TEXT,
        recruiter_contact TEXT,
        source_domain TEXT,
        source_tier TEXT,
        relevance_score REAL,
        quality_score REAL,
        first_seen TEXT,
        expires_at TEXT
    );

    CREATE TABLE IF NOT EXISTS strategies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT,
        queries_json TEXT,
        sources_json TEXT,
        reasoning TEXT,
        confidence REAL,
        active INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id INTEGER,
        started_at TEXT,
        finished_at TEXT,
        fetched INTEGER DEFAULT 0,
        kept INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS failures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        strategy_id INTEGER,
        query TEXT,
        domain TEXT,
        error_type TEXT,
        error_msg TEXT,
        created_at TEXT
    );
    """)
    conn.commit()


def insert_job(job: dict[str, Any]) -> int:
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO jobs (title, company, location, posted_date, url,
            description_full, recruiter_name, recruiter_title,
            recruiter_contact, source_domain, source_tier,
            relevance_score, quality_score, first_seen, expires_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        job.get("title"), job.get("company"), job.get("location"),
        job.get("posted_date"), job.get("url"),
        job.get("description_full"),
        job.get("recruiter_name"), job.get("recruiter_title"),
        job.get("recruiter_contact"), job.get("source_domain"),
        job.get("source_tier"), job.get("relevance_score"),
        job.get("quality_score"),
        datetime.datetime.utcnow().isoformat(),
        job.get("expires_at"),
    ))
    conn.commit()
    return cur.lastrowid


def get_jobs(limit: int = 200, date_from: str | None = None,
             date_to: str | None = None, location: str | None = None):
    conn = get_conn()
    q = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if date_from:
        q += " AND posted_date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND posted_date <= ?"
        params.append(date_to)
    if location:
        q += " AND location LIKE ?"
        params.append(f"%{location}%")
    q += " ORDER BY first_seen DESC LIMIT ?"
    params.append(limit)
    return conn.execute(q, params).fetchall()


def delete_jobs_by_date(cutoff_iso: str) -> int:
    """Retention: delete records older than cutoff. Returns rows deleted."""
    conn = get_conn()
    cur = conn.execute("DELETE FROM jobs WHERE first_seen < ?", (cutoff_iso,))
    conn.commit()
    return cur.rowcount


def save_strategy(queries: list, sources: list, reasoning: str,
                  confidence: float, active: bool = True) -> int:
    conn = get_conn()
    conn.execute("UPDATE strategies SET active = 0")
    cur = conn.execute("""
        INSERT INTO strategies (created_at, queries_json, sources_json,
            reasoning, confidence, active)
        VALUES (?,?,?,?,?,?)
    """, (
        datetime.datetime.utcnow().isoformat(),
        json.dumps(queries), json.dumps(sources),
        reasoning, confidence, 1 if active else 0,
    ))
    conn.commit()
    return cur.lastrowid


def get_active_strategy():
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM strategies WHERE active = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row:
        return {
            "id": row[0], "created_at": row[1],
            "queries": json.loads(row[2]) if row[2] else [],
            "sources": json.loads(row[3]) if row[3] else [],
            "reasoning": row[4], "confidence": row[5],
        }
    return None


def start_run(strategy_id: int) -> int:
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO runs (strategy_id, started_at, fetched, kept, errors)
        VALUES (?,?,0,0,0)
    """, (strategy_id, datetime.datetime.utcnow().isoformat()))
    conn.commit()
    return cur.lastrowid


def finish_run(run_id: int, fetched: int, kept: int, errors: int):
    conn = get_conn()
    conn.execute("""
        UPDATE runs SET finished_at = ?, fetched = ?, kept = ?, errors = ?
        WHERE id = ?
    """, (datetime.datetime.utcnow().isoformat(), fetched, kept, errors, run_id))
    conn.commit()


def log_failure(strategy_id: int, query: str, domain: str,
                error_type: str, error_msg: str):
    conn = get_conn()
    conn.execute("""
        INSERT INTO failures (strategy_id, query, domain, error_type,
            error_msg, created_at)
        VALUES (?,?,?,?,?,?)
    """, (strategy_id, query, domain, error_type,
          error_msg[:500], datetime.datetime.utcnow().isoformat()))
    conn.commit()


def recent_failures(strategy_id: int, limit: int = 20):
    conn = get_conn()
    return conn.execute("""
        SELECT query, domain, error_type, error_msg
        FROM failures WHERE strategy_id = ?
        ORDER BY id DESC LIMIT ?
    """, (strategy_id, limit)).fetchall()
