# prices_db.py
# All DB access for the Live Prices feature. Reuses db.py's D1 connection.

import json
import datetime
import logging
import threading

import db as _db

logger = logging.getLogger(__name__)
_lock = threading.RLock()


def _utcnow():
    return datetime.datetime.utcnow().isoformat()


def _exec(sql, params=()):
    return _db._exec(sql, params)


def _write(sql, params=()):
    return _db._write(sql, params)


# ---------------- state ----------------
def get_state(key, default=""):
    try:
        row = _exec("SELECT value FROM price_state WHERE key=?", (key,)).fetchone()
        return row[0] if row else default
    except Exception as e:
        logger.warning("price_state get %s failed: %s", key, e)
        return default


def set_state(key, value):
    try:
        _write("""
            INSERT INTO price_state (key, value, updated_at) VALUES (?,?,?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                updated_at=excluded.updated_at
        """, (key, str(value), _utcnow()))
    except Exception as e:
        logger.warning("price_state set %s failed: %s", key, e)


# ---------------- sources ----------------
def add_source(name, url, kind="html"):
    name = (name or "").strip()[:120]
    url = (url or "").strip()[:500]
    if not name or not url:
        return False
    try:
        ex = _exec("SELECT id FROM price_sources WHERE url=?", (url,)).fetchone()
        if ex:
            return False
        _write("""
            INSERT INTO price_sources (name, url, kind, active, created_at)
            VALUES (?,?,?,1,?)
        """, (name, url, kind, _utcnow()))
        return True
    except Exception as e:
        logger.warning("add_source failed: %s", e)
        return False


def list_sources(limit=200):
    try:
        return _exec("""
            SELECT id, name, url, kind, active, last_run_at, last_status
            FROM price_sources ORDER BY id DESC LIMIT ?
        """, (limit,)).fetchall()
    except Exception:
        return []


def delete_source(sid):
    try:
        _write("DELETE FROM price_sources WHERE id=?", (sid,))
    except Exception:
        pass


def next_sources_to_run(n=5):
    try:
        return _exec("""
            SELECT id, name, url, kind FROM price_sources
            WHERE active=1
            ORDER BY COALESCE(last_run_at, '1970-01-01') ASC
            LIMIT ?
        """, (n,)).fetchall()
    except Exception:
        return []


def mark_source_run(sid, status):
    try:
        _write("""
            UPDATE price_sources
            SET last_run_at=?, last_status=? WHERE id=?
        """, (_utcnow(), (status or "")[:200], sid))
    except Exception:
        pass


def source_stats():
    try:
        total = _exec("SELECT COUNT(*) FROM price_sources").fetchone()[0]
        active = _exec("SELECT COUNT(*) FROM price_sources WHERE active=1").fetchone()[0]
        return {"total": total, "active": active}
    except Exception:
        return {"total": 0, "active": 0}


# ---------------- categories ----------------
def find_category_by_slug(slug):
    try:
        return _exec("SELECT id, name, slug FROM price_categories WHERE slug=?",
                     (slug,)).fetchone()
    except Exception:
        return None


def add_category(name, parent_id=None, source="ai", confidence=0.6):
    slug = _slugify(name)
    if not slug:
        return None
    try:
        existing = find_category_by_slug(slug)
        if existing:
            return existing[0]
        cur = _write("""
            INSERT INTO price_categories (parent_id, name, slug, confidence, source, created_at)
            VALUES (?,?,?,?,?,?)
        """, (parent_id, name[:120], slug, confidence, source, _utcnow()))
        return cur.lastrowid
    except Exception as e:
        logger.warning("add_category failed: %s", e)
        return None


def all_categories(parent_id=None):
    try:
        if parent_id is None:
            return _exec("""
                SELECT id, parent_id, name, slug, confidence
                FROM price_categories
                WHERE parent_id IS NULL
                ORDER BY name
            """).fetchall()
        return _exec("""
            SELECT id, parent_id, name, slug, confidence
            FROM price_categories WHERE parent_id=?
            ORDER BY name
        """, (parent_id,)).fetchall()
    except Exception:
        return []


# ---------------- regions ----------------
def add_region(name):
    name = (name or "").strip()[:120]
    if not name:
        return None
    slug = _slugify(name)
    try:
        ex = _exec("SELECT id FROM price_regions WHERE name=?", (name,)).fetchone()
        if ex:
            return ex[0]
        cur = _write("""
            INSERT INTO price_regions (name, slug, created_at) VALUES (?,?,?)
        """, (name, slug, _utcnow()))
        return cur.lastrowid
    except Exception:
        return None


def all_regions():
    try:
        return _exec("SELECT id, name FROM price_regions ORDER BY name").fetchall()
    except Exception:
        return []


# ---------------- materials ----------------
def add_material(category_id, name, unit=None, spec=None):
    name = (name or "").strip()[:200]
    if not name:
        return None
    try:
        ex = _exec("""
            SELECT id FROM price_materials
            WHERE name=? AND COALESCE(spec,'')=COALESCE(?,'')
            LIMIT 1
        """, (name, spec or None)).fetchone()
        if ex:
            return ex[0]
        cur = _write("""
            INSERT INTO price_materials (category_id, name, unit, spec, created_at)
            VALUES (?,?,?,?,?)
        """, (category_id, name, unit, spec, _utcnow()))
        return cur.lastrowid
    except Exception as e:
        logger.warning("add_material failed: %s", e)
        return None


def materials_by_category(category_id, limit=500):
    try:
        return _exec("""
            SELECT id, name, unit, spec FROM price_materials
            WHERE category_id=? ORDER BY name LIMIT ?
        """, (category_id, limit)).fetchall()
    except Exception:
        return []


# ---------------- observations ----------------
def add_observation(material_id, region_id, source_id, price,
                    currency="EGP", unit=None, confidence=0.5, raw=None):
    try:
        cur = _write("""
            INSERT INTO price_observations
              (material_id, region_id, source_id, price, currency, unit,
               observed_at, raw_json, confidence, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (material_id, region_id, source_id, float(price),
              currency or "EGP", unit, _utcnow(),
              (json.dumps(raw) if raw else "")[:2000],
              float(confidence), _utcnow()))
        return cur.lastrowid
    except Exception as e:
        logger.warning("add_observation failed: %s", e)
        return None


def recent_observations(limit=50):
    try:
        return _exec("""
            SELECT o.id, m.name AS material, m.spec, o.price, o.currency,
                   o.unit, r.name AS region, s.name AS source_name,
                   o.confidence, o.approved, o.rejected, o.created_at
            FROM price_observations o
            LEFT JOIN price_materials m ON m.id = o.material_id
            LEFT JOIN price_regions r ON r.id = o.region_id
            LEFT JOIN price_sources s ON s.id = o.source_id
            ORDER BY o.id DESC LIMIT ?
        """, (limit,)).fetchall()
    except Exception:
        return []


def approve_observation(oid):
    try:
        obs = _exec("""
            SELECT material_id, region_id FROM price_observations WHERE id=?
        """, (oid,)).fetchone()
        if not obs:
            return False
        _write("UPDATE price_observations SET approved=1, rejected=0 WHERE id=?",
               (oid,))
        _recompute_summary(obs[0], obs[1])
        return True
    except Exception:
        return False


def reject_observation(oid):
    try:
        obs = _exec("""
            SELECT material_id, region_id FROM price_observations WHERE id=?
        """, (oid,)).fetchone()
        if not obs:
            return False
        _write("UPDATE price_observations SET approved=0, rejected=1 WHERE id=?",
               (oid,))
        _recompute_summary(obs[0], obs[1])
        return True
    except Exception:
        return False


def delete_observation(oid):
    try:
        _write("DELETE FROM price_observations WHERE id=?", (oid,))
        return True
    except Exception:
        return False


def _recompute_summary(material_id, region_id):
    try:
        row = _exec("""
            SELECT MIN(price), MAX(price), AVG(price), COUNT(*), AVG(confidence)
            FROM price_observations
            WHERE material_id=? AND COALESCE(region_id,0)=COALESCE(?,0)
              AND approved=1
        """, (material_id, region_id or 0)).fetchone()
        if not row or not row[3]:
            return
        low, high, avg, n, conf = row
        _write("""
            INSERT INTO price_summary
              (material_id, region_id, price_low, price_high, price_avg,
               confidence, sources_count, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(material_id, region_id) DO UPDATE SET
              price_low=excluded.price_low,
              price_high=excluded.price_high,
              price_avg=excluded.price_avg,
              confidence=excluded.confidence,
              sources_count=excluded.sources_count,
              updated_at=excluded.updated_at
        """, (material_id, region_id or None, low, high, avg,
              conf or 0.5, n, _utcnow()))
    except Exception as e:
        logger.warning("recompute_summary failed: %s", e)


# ---------------- search / summary ----------------
def search_prices(query="", category_id=None, region_id=None,
                  min_price=None, max_price=None, limit=200):
    """Return joined material summary rows with all filters."""
    sql = """
        SELECT m.id, m.name, m.spec, m.unit,
               c.name AS category, r.name AS region,
               s.price_low, s.price_high, s.price_avg,
               s.confidence, s.sources_count
        FROM price_materials m
        LEFT JOIN price_categories c ON c.id = m.category_id
        LEFT JOIN price_summary s   ON s.material_id = m.id
        LEFT JOIN price_regions r   ON r.id = s.region_id
        WHERE 1=1
    """
    params = []
    if query:
        sql += " AND (m.name LIKE ? OR m.spec LIKE ?)"
        like = f"%{query}%"
        params += [like, like]
    if category_id:
        sql += " AND m.category_id = ?"
        params.append(category_id)
    if region_id:
        sql += " AND s.region_id = ?"
        params.append(region_id)
    if min_price is not None:
        sql += " AND s.price_avg >= ?"
        params.append(float(min_price))
    if max_price is not None:
        sql += " AND s.price_avg <= ?"
        params.append(float(max_price))
    sql += " ORDER BY m.name LIMIT ?"
    params.append(int(limit))
    try:
        return _exec(sql, tuple(params)).fetchall()
    except Exception as e:
        logger.warning("search_prices failed: %s", e)
        return []


def price_stats():
    try:
        obs = _exec("SELECT COUNT(*) FROM price_observations").fetchone()[0]
        pending = _exec(
            "SELECT COUNT(*) FROM price_observations WHERE approved=0 AND rejected=0"
        ).fetchone()[0]
        mats = _exec("SELECT COUNT(*) FROM price_materials").fetchone()[0]
        cats = _exec("SELECT COUNT(*) FROM price_categories").fetchone()[0]
        regions = _exec("SELECT COUNT(*) FROM price_regions").fetchone()[0]
        approved = _exec(
            "SELECT COUNT(*) FROM price_observations WHERE approved=1"
        ).fetchone()[0]
        return {"observations": obs, "pending": pending, "approved": approved,
                "materials": mats, "categories": cats, "regions": regions}
    except Exception:
        return {"observations": 0, "pending": 0, "approved": 0,
                "materials": 0, "categories": 0, "regions": 0}


# ---------------- helpers ----------------
def _slugify(s):
    import re
    s = (s or "").strip().lower()
    if " / " in s:
        s = s.split(" / ", 1)[0]
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:80]
