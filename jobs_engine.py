# jobs_engine.py — HUBx Job Board Scraper
# Scrapes ONLY admin-entered URLs. Never discovers URLs on its own.
# Flow: job_sources (D1) → fetch list page → collect direct posting links
#       → open each posting → Groq summarize → job_postings (D1).

from __future__ import annotations

import asyncio
import json
import time
import traceback

import db as _db
import jobs_db as _jdb
import jobs_gemini as _jg
from jobs_fetcher import fetch_page

PAUSED_KEY = "jobs_engine_paused"
STATE_KEY = "jobs_engine_state"          # running / paused / cooling
COOLDOWN_KEY = "jobs_cooldown_until"     # unix ts as string

# Crawl every 30 minutes; 1 source per cycle keeps Groq usage tiny.
CRAWL_INTERVAL_SECONDS = 30 * 60

# Cap on how many individual postings we summarize per source per cycle.
MAX_POSTINGS_PER_SOURCE = 5

# If Groq returns 429 → 30 min cooldown.
QUOTA_COOLDOWN_SECONDS = 30 * 60

# Shared daily/hourly Groq gate (same values as the other engines).
GROQ_DAY_LIMIT = 600
GROQ_HOUR_LIMIT = 40


class JobsEngine:
    def __init__(self):
        self.running = False
        self.paused = True
        self.cycles = 0
        self.calls = 0
        self.jobs_scraped = 0
        self.last_source = ""
        self.last_status = "idle"
        self.last_error = ""
        self.last_debug = ""
        self._task = None
        self._wake = asyncio.Event()
        self._lock = asyncio.Lock()
        self._quota_block_until = 0.0

    # ── lifecycle ───────────────────────────────────────────────────────
    async def start(self, by_user=True):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.last_status = "running"
        self.last_debug = "started"
        if by_user:
            _jdb.set_state(PAUSED_KEY, "0")
            _jdb.set_state(STATE_KEY, "running")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        else:
            self._wake.set()

    async def pause(self):
        self.running = False
        self.paused = True
        self.last_status = "paused"
        self.last_debug = "paused"
        _jdb.set_state(PAUSED_KEY, "1")
        _jdb.set_state(STATE_KEY, "paused")
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

    # ── one cycle ───────────────────────────────────────────────────────
    async def _cycle(self):
        async with self._lock:
            if time.monotonic() < self._quota_block_until:
                return

            self.last_status = "running"
            sources = _jdb.next_sources_to_run(n=1)
            if not sources:
                self.last_debug = "no active sources"
                return

            for src in sources:
                sid, name, url, kind = src[0], src[1], src[2], src[3]
                await self._process_source(sid, name, url, kind)

    async def _process_source(self, sid, name, url, kind):
        self.last_source = name
        self.last_debug = f"fetching list: {name}"
        ok, final_url, text_or_err, links = await asyncio.to_thread(
            fetch_page, url, kind)
        if not ok:
            _jdb.mark_source_run(sid, f"fetch_error: {text_or_err[:100]}")
            self.last_debug = f"fetch failed: {name} — {text_or_err[:80]}"
            self.last_error = text_or_err
            return

        if not links:
            _jdb.mark_source_run(sid, "no_links_found")
            self.last_debug = f"no posting links on {name}"
            return

        self.last_debug = f"{name}: {len(links)} candidate links"

        summarized = 0
        for link in links[:MAX_POSTINGS_PER_SOURCE]:
            # Shared Groq gate — the same one all engines use.
            if not _db.check_and_increment_gemini_usage(
                    day_limit=GROQ_DAY_LIMIT,
                    hour_limit=GROQ_HOUR_LIMIT):
                self.last_debug = "groq gate blocked (quota)"
                self.last_status = "cooling"
                _jdb.set_state(STATE_KEY, "cooling")
                break

            ok2, final2, txt2, _ = await asyncio.to_thread(
                fetch_page, link, kind)
            if not ok2 or len(txt2) < 400:
                continue

            try:
                result = await _jg.summarize_job(txt2, final2, name)
            except Exception as e:
                self.last_error = f"summarize: {e}"
                result = {"error": "summarize_exception"}
            self.calls += 1

            err_lower = (_jg.last_error or "").lower()
            if "429" in err_lower or "quota" in err_lower:
                self._quota_block_until = (
                    time.monotonic() + QUOTA_COOLDOWN_SECONDS)
                self.last_debug = "Groq 429 — cooling down 30m"
                self.last_error = _jg.last_error
                self.last_status = "cooling"
                _jdb.set_state(STATE_KEY, "cooling")
                _jdb.set_state(
                    COOLDOWN_KEY,
                    str(int(time.time() + QUOTA_COOLDOWN_SECONDS)))
                _jdb.mark_source_run(sid, "quota_cooldown")
                return

            if result.get("error"):
                continue

            pid = _jdb.add_posting(sid, result)
            if pid:
                summarized += 1
                self.jobs_scraped += 1

        status = f"ok: {summarized} new"
        _jdb.mark_source_run(sid, status)
        self.last_debug = f"{name}: {summarized} new postings"

    # ── stats ───────────────────────────────────────────────────────────
    def stats(self):
        s = _jdb.jobs_stats()
        src = _jdb.source_stats()
        # Cooldown seconds remaining.
        try:
            cd_until = int(_jdb.get_state(COOLDOWN_KEY, "0") or "0")
            cd_left = max(0, cd_until - int(time.time()))
        except Exception:
            cd_left = 0
        return {
            "cycles": self.cycles,
            "calls": self.calls,
            "jobs_scraped": self.jobs_scraped,
            "postings": s["postings"],
            "last_7_days": s["last_7_days"],
            "companies": s["companies"],
            "sources_total": src["total"],
            "sources_active": src["active"],
            "last_source": self.last_source,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_debug": self.last_debug,
            "cooldown_left": cd_left,
        }


jobs_engine = JobsEngine()


async def auto_start_jobs_if_needed():
    try:
        paused = _jdb.get_state(PAUSED_KEY, "1")
    except Exception:
        paused = "1"
    if str(paused) == "1":
        jobs_engine.paused = True
        jobs_engine.running = False
        jobs_engine.last_status = "paused"
        print("[jobs_engine] auto-start skipped")
        return
    print("[jobs_engine] auto-starting")
    await jobs_engine.start(by_user=False)
