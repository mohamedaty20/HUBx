# prices_engine.py
# Self-learning price crawler loop.
# v2: much slower cadence, 429-aware cooldown, shared daily quota.

from __future__ import annotations
import asyncio
import time
import traceback

import db as _db
import prices_db as _pdb
import prices_gemini as _pg
from prices_fetcher import fetch_page
from prices_sources import SEED_PRICE_SOURCES

PAUSED_KEY = "prices_crawler_paused"

# Crawl every 20 minutes. Matches the careful pacing of the
# knowledge/templates engines so we never burn the Groq quota.
CRAWL_INTERVAL_SECONDS = 20 * 60  # 1200s

# Only 1 source per cycle — keeps each cycle small.
BATCH_SIZE = 1

# If Groq returns 429, pause for 30 minutes before trying again.
QUOTA_COOLDOWN_SECONDS = 30 * 60


class PricesEngine:
    def __init__(self):
        self.running = False
        self.paused = True
        self.cycles = 0
        self.calls = 0
        self.observations = 0
        self.last_status = "idle"
        self.last_error = ""
        self.last_debug = ""
        self._task = None
        self._wake = asyncio.Event()
        self._lock = asyncio.Lock()
        self._seed_idx = 0
        self._quota_block_until = 0.0

    async def start(self, by_user=True):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.last_status = "running"
        self.last_debug = "started"
        if by_user:
            _pdb.set_state(PAUSED_KEY, "0")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        else:
            self._wake.set()

    async def pause(self):
        self.running = False
        self.paused = True
        self.last_status = "paused"
        self.last_debug = "paused"
        _pdb.set_state(PAUSED_KEY, "1")
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    async def _loop(self):
        try:
            while self.running:
                t0 = asyncio.get_event_loop().time()
                try:
                    await self._cycle()
                    self.cycles += 1
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = f"{type(e).__name__}: {e}"
                    self.last_debug = f"cycle error: {e}"
                    traceback.print_exc()
                if not self.running:
                    break

                # If we are in quota cooldown, wait that long instead.
                now = time.monotonic()
                if now < self._quota_block_until:
                    wait = self._quota_block_until - now
                    self.last_debug = f"quota cooldown ({int(wait)}s left)"
                else:
                    elapsed = asyncio.get_event_loop().time() - t0
                    wait = max(0.0, CRAWL_INTERVAL_SECONDS - elapsed)

                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=wait)
                    self._wake.clear()
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            self.last_status = "paused"
            raise

    async def _cycle(self):
        async with self._lock:
            # Respect a prior 429 cooldown.
            if time.monotonic() < self._quota_block_until:
                return

            self.last_status = "running"
            sources = _pdb.next_sources_to_run(n=BATCH_SIZE)
            if not sources:
                if _pdb.source_stats()["total"] == 0:
                    self.last_debug = "seeding sources…"
                    for name, url, kind in SEED_PRICE_SOURCES:
                        _pdb.add_source(name, url, kind)
                    self.last_debug = f"seeded {len(SEED_PRICE_SOURCES)} sources"
                    return
                name, url, kind = SEED_PRICE_SOURCES[
                    self._seed_idx % len(SEED_PRICE_SOURCES)]
                self._seed_idx += 1
                sources = [(0, name, url, kind)]

            for src in sources:
                sid, name, url, kind = src[0], src[1], src[2], src[3]
                await self._process_source(sid, name, url)

    async def _process_source(self, sid, name, url):
        self.last_debug = f"fetching: {name}"
        ok, text_or_err = await asyncio.to_thread(fetch_page, url)
        if not ok:
            if sid:
                _pdb.mark_source_run(sid, f"fetch_error: {text_or_err[:100]}")
            self.last_debug = f"fetch failed: {name} — {text_or_err[:80]}"
            self.last_error = text_or_err
            return

        # Skip useless pages before spending a token.
        if len(text_or_err) < 400:
            if sid:
                _pdb.mark_source_run(sid, "skip: page too short")
            self.last_debug = f"skip: {name} (short)"
            return

        self.last_debug = f"extracting: {name} ({len(text_or_err)} chars)"
        existing_cats = [c[2] for c in _pdb.all_categories()]
        result = await _pg.extract_prices(text_or_err, name, existing_cats)
        self.calls += 1

        # If Groq returned a 429, back off for 30 minutes.
        err_lower = (_pg.last_error or "").lower()
        if "429" in err_lower or "quota" in err_lower or "cooling" in err_lower:
            self._quota_block_until = time.monotonic() + QUOTA_COOLDOWN_SECONDS
            self.last_debug = "Groq 429 — cooling down 30m"
            self.last_error = _pg.last_error
            if sid:
                _pdb.mark_source_run(sid, "quota_cooldown")
            return

        for rn in (result.get("new_regions") or []):
            _pdb.add_region(rn)

        for c in (result.get("new_categories") or []):
            parent_id = None
            parent_name = c.get("parent")
            if parent_name:
                parent_row = _pdb.find_category_by_slug(
                    _pdb._slugify(parent_name))
                if parent_row:
                    parent_id = parent_row[0]
                else:
                    parent_id = _pdb.add_category(
                        parent_name, None, "ai", 0.5)
            _pdb.add_category(c["name"], parent_id, "ai", 0.6)

        inserted = 0
        for p in (result.get("prices") or []):
            cat_id = None
            mat_lower = p["material"].lower()
            all_cats = _pdb.all_categories()
            for c in all_cats:
                if c[2] and c[2].lower() in mat_lower:
                    cat_id = c[0]
                    break
            mat_id = _pdb.add_material(cat_id, p["material"],
                                       p.get("unit"), p.get("spec"))
            if not mat_id:
                continue
            region_id = _pdb.add_region(p["region"]) if p.get("region") else None
            _pdb.add_observation(
                mat_id, region_id, sid or None, p["price"],
                p.get("currency", "EGP"), p.get("unit"),
                p.get("confidence", 0.5), p)
            inserted += 1
            self.observations += 1

        status = f"ok: {inserted} observations"
        if sid:
            _pdb.mark_source_run(sid, status)
        self.last_debug = f"{name}: {inserted} observations"

    def stats(self):
        st = _pdb.price_stats()
        return {
            "cycles": self.cycles,
            "calls": self.calls,
            "observations": self.observations,
            "pending": st["pending"],
            "approved": st["approved"],
            "materials": st["materials"],
            "categories": st["categories"],
            "regions": st["regions"],
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_debug": self.last_debug,
        }


prices_engine = PricesEngine()


async def auto_start_prices_if_needed():
    try:
        paused = _pdb.get_state(PAUSED_KEY, "1")
    except Exception:
        paused = "1"
    if str(paused) == "1":
        prices_engine.paused = True
        prices_engine.running = False
        prices_engine.last_status = "paused"
        print("[prices_engine] auto-start skipped")
        return
    print("[prices_engine] auto-starting")
    await prices_engine.start(by_user=False)
