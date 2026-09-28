# jobs_db.py — HUBx Job Board Scraper
# All DB access for the Jobs feature. Reuses db.py's D1 connection.

import json
import datetime
import logging

import db as _db

logger = logging.getLogger(__name__)


def _utcnow():
    return datetime.datetime.utcnow().isoformat()


def _exec(sql, params=()):
    return _db._exec(sql, params)


def _write(sql, params=()):
    return _db._write(sql, params)


# ── state (reuses price_state table) ─────────────────────────────────────
def get_state(key, default=""):
    try:
        row = _exec("SELECT value FROM price_state WHERE key=?",
                    (key,)).fetchone()
        return row[0] if row else default
    except Exception as e:
        logger.warning("jobs get_state %s failed: %s", key, e)
        return default


def set_state(key, value):
    try:
        _write("""
            INSERT INTO price_state (key, value, updated_at) VALUES (?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                updated_at=excluded.updated_at
        """, (key, str(value), _utcnow()))
    except Exception as e:
        logger.warning("jobs set_state %s failed: %s", key, e)


# ── sources ──────────────────────────────────────────────────────────────
def add_source(name, url, kind="html"):
    name = (name or "").strip()[:120]
    url = (url or "").strip()[:500]
    kind = "js" if (kind or "").strip().lower() == "js" else "html"
    if not name or not url:
        return False
    try:
        ex = _exec("SELECT id FROM job_sources WHERE url=?",
                   (url,)).fetchone()
        if ex:
            return False
        _write("""
            INSERT INTO job_sources (name, url, kind, active, created_at)
            VALUES (?,?,?,1,?)
        """, (name, url, kind, _utcnow()))
        return True
    except Exception as e:
        logger.warning("jobs add_source failed: %s", e)
        return False


def list_sources(limit=200):
    try:
        return _exec("""
            SELECT id, name, url, kind, active, last_run_at, last_status
            FROM job_sources ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    except Exception:
        return []


def delete_source(sid):
    try:
        _write("DELETE FROM job_sources WHERE id=?", (sid,))
    except Exception:
        pass


def toggle_source(sid):
    try:
        row = _exec("SELECT active FROM job_sources WHERE id=?",
                    (sid,)).fetchone()
        if not row:
            return False
        new_val = 0 if int(row[0] or 0) else 1
        _write("UPDATE job_sources SET active=? WHERE id=?",
               (new_val, sid))
        return True
    except Exception:
        return False


def next_sources_to_run(n=1):
    try:
        return _exec("""
            SELECT id, name, url, kind FROM job_sources
            WHERE active=1
            ORDER BY COALESCE(last_run_at, '1970-01-01') ASC
            LIMIT ?
        """, (n,)).fetchall()
    except Exception:
        return []


def mark_source_run(sid, status):
    try:
        _write("""
            UPDATE job_sources
            SET last_run_at=?, last_status=? WHERE id=?
        """, (_utcnow(), (status or "")[:200], sid))
    except Exception:
        pass


def source_stats():
    try:
        total = _exec("SELECT COUNT(*) FROM job_sources").fetchone()[0]
        active = _exec(
            "SELECT COUNT(*) FROM job_sources WHERE active=1"
        ).fetchone()[0]
        return {"total": total, "active": active}
    except Exception:
        return {"total": 0, "active": 0}


# ── postings ─────────────────────────────────────────────────────────────
def add_posting(source_id, data):
    """Insert a summarized posting. Returns the new id, or None if
    the apply_url already exists (INSERT OR IGNORE → no row)."""
    apply_url = (data.get("apply_url") or "").strip()[:800]
    title = (data.get("title") or "").strip()[:200]
    if not apply_url or not title:
        return None
    try:
        cur = _write("""
            INSERT OR IGNORE INTO job_postings
              (source_id, title, company, location, employment_type,
               experience_level, posted_date, posted_date_confidence,
               apply_url, summary_points, requirements_points,
               key_skills, scraped_at, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            source_id,
            title,
            (data.get("company") or "")[:200],
            (data.get("location") or "")[:200],
            (data.get("employment_type") or "unknown")[:40],
            (data.get("experience_level") or "unknown")[:40],
            (data.get("posted_date") or "")[:32],
            float(data.get("posted_date_confidence") or 0.0),
            apply_url,
            json.dumps(data.get("summary_points") or [])[:4000],
            json.dumps(data.get("requirements_points") or [])[:4000],
            json.dumps(data.get("key_skills") or [])[:1500],
            _utcnow(),
            _utcnow(),
        ))
        # INSERT OR IGNORE on a UNIQUE conflict returns lastrowid == 0
        # in D1, so detect duplicates via a SELECT.
        if cur.lastrowid:
            return cur.lastrowid
        return None
    except Exception as e:
        logger.warning("jobs add_posting failed: %s", e)
        return None


def delete_posting(pid):
    try:
        _write("DELETE FROM job_postings WHERE id=?", (pid,))
        return True
    except Exception:
        return False


def reset_postings():
    try:
        _write("DELETE FROM job_postings", ())
        return True
    except Exception:
        return False


def recent_postings(limit=50):
    try:
        return _exec("""
            SELECT p.id, p.title, p.company, p.location, p.posted_date,
                   p.apply_url, p.scraped_at
            FROM job_postings p
            ORDER BY p.id DESC LIMIT ?
        """, (limit,)).fetchall()
    except Exception:
        return []


def count_postings():
    try:
        return _exec("SELECT COUNT(*) FROM job_postings").fetchone()[0]
    except Exception:
        return 0


def jobs_stats():
    try:
        total = _exec("SELECT COUNT(*) FROM job_postings").fetchone()[0]
        last7 = _exec("""
            SELECT COUNT(*) FROM job_postings
            WHERE scraped_at >= ?
        """, ((datetime.datetime.utcnow()
               - datetime.timedelta(days=7)).isoformat(),)).fetchone()[0]
        companies = _exec("""
            SELECT COUNT(DISTINCT company) FROM job_postings
            WHERE company IS NOT NULL AND company != ''
        """).fetchone()[0]
        return {"postings": total, "last_7_days": last7,
                "companies": companies}
    except Exception:
        return {"postings": 0, "last_7_days": 0, "companies": 0}
