# engine.py
# 70-second loop with pause/start, cancellation, counters.
# Pause is REAL: when paused, no Gemini call is initiated, and any
# in-flight call's response is discarded, not stored.

import asyncio
import datetime
import logging
from typing import Optional

import feedparser

from sources import SOURCES, LIVE_FETCH_URLS, get_tier
from compliance import safe_fetch, ComplianceError
from db import (get_active_strategy, save_strategy, start_run, finish_run,
                log_failure, insert_job, recent_failures)
from gemini import refine_strategy

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CYCLE_INTERVAL = 70
REFINE_EVERY_N = 5
MAX_JOBS_PER_CYCLE = 50
MAX_AGE_DAYS = 7


class Engine:
    def __init__(self):
        self.running = False
        self.paused = True
        self.cycles_completed = 0
        self.gemini_calls = 0
        self.last_status = "idle"
        self.last_error = ""
        self.last_debug = ""  # human-readable per-cycle summary
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        if self._task and not self._task.done():
            return
        self.paused = False
        self.running = True
        self._task = asyncio.create_task(self._loop())
        self.last_status = "started"

    async def pause(self):
        self.paused = True
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        self.last_status = "paused"

    async def _loop(self):
        try:
            while not self.paused:
                try:
                    await self._cycle()
                    self.cycles_completed += 1
                    self.last_status = f"cycle {self.cycles_completed} done"
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = str(e)
                    self.last_status = f"error: {e}"
                    logger.exception("Cycle error")

                for _ in range(CYCLE_INTERVAL):
                    if self.paused:
                        return
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Engine loop cancelled.")
            raise

    async def _cycle(self):
        strategy = get_active_strategy()
        if not strategy:
            save_strategy(
                queries=["civil engineer Egypt", "structural engineer Cairo"],
                sources=[d for d, t in SOURCES.items() if t in ("A", "B")],
                reasoning="bootstrap default",
                confidence=0.5,
            )
            strategy = get_active_strategy()

        strategy_id = strategy["id"]
        run_id = start_run(strategy_id)
        fetched = kept = errors = 0
        debug_lines = []

        try:
            for domain in strategy.get("sources", []):
                if self.paused:
                    break
                url = LIVE_FETCH_URLS.get(domain)
                if not url:
                    debug_lines.append(f"{domain}: no live URL configured")
                    continue
                try:
                    text = await safe_fetch(url)
                    fetched += 1
                    all_jobs = self._parse_feed_or_html(text, domain)
                    kept_before = kept

                    for job in all_jobs[:MAX_JOBS_PER_CYCLE]:
                        if self.paused:
                            break

                        # Normalize posted_date to ISO YYYY-MM-DD; discard unknown.
                        iso_date = self._normalize_date(job.get("posted_date"))
                        if not iso_date:
                            continue

                        # Reject anything older than MAX_AGE_DAYS.
                        if not self._within_window(iso_date, MAX_AGE_DAYS):
                            continue

                        if not self._is_egypt_civil(job):
                            continue

                        job["posted_date"] = iso_date
                        job["source_domain"] = domain
                        job["source_tier"] = get_tier(domain)
                        insert_job(job)
                        kept += 1

                    debug_lines.append(
                        f"{domain}: {len(all_jobs)} entries, "
                        f"{kept - kept_before} kept"
                    )
                except ComplianceError as e:
                    errors += 1
                    debug_lines.append(f"{domain}: compliance error - {e}")
                    log_failure(strategy_id, "", domain, "compliance", str(e))
                except Exception as e:
                    errors += 1
                    debug_lines.append(f"{domain}: fetch error - {e}")
                    log_failure(strategy_id, "", domain, "fetch", str(e))

            self.last_debug = " | ".join(debug_lines) or "no sources configured"

            if (self.cycles_completed + 1) % REFINE_EVERY_N == 0 and not self.paused:
                await self._refine(strategy_id, strategy)

        finally:
            finish_run(run_id, fetched, kept, errors)

    async def _refine(self, strategy_id: int, strategy: dict):
        if self.paused:
            return
        failures = recent_failures(strategy_id, 20)
        today = datetime.date.today().isoformat()
        allowed = {d: t for d, t in SOURCES.items() if t in ("A", "B")}

        self.gemini_calls += 1
        result = await refine_strategy(today, strategy, failures, allowed)

        if self.paused:
            logger.info("Discarding Gemini refinement - paused during call.")
            return
        if not result:
            return

        save_strategy(
            queries=result.get("queries", strategy.get("queries", [])),
            sources=result.get("sources", strategy.get("sources", [])),
            reasoning=result.get("reasoning", ""),
            confidence=float(result.get("confidence", 0.5)),
        )

    # ------------------------------------------------------------------
    # Parsing + filtering helpers (plain Python, no AI)
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_feed_or_html(text: str, domain: str) -> list[dict]:
        jobs = []
        feed = feedparser.parse(text)
        for entry in feed.entries[:100]:
            jobs.append({
                "title": entry.get("title", ""),
                "company": entry.get("author", ""),
                "location": entry.get("location", "")
                            or Engine._location_from_tags(entry),
                "posted_date": entry.get("published", "")
                               or entry.get("updated", ""),
                "url": entry.get("link", ""),
                "description_full": entry.get("summary", ""),
                "recruiter_name": "",
                "recruiter_title": "",
                "recruiter_contact": "",
            })
        return jobs

    @staticmethod
    def _location_from_tags(entry) -> str:
        """Pull a location hint from feed tags if the entry doesn't have one."""
        tags = entry.get("tags", []) or []
        for t in tags:
            term = (t.get("term") or "").strip()
            if any(k in term.lower() for k in (
                    "egypt", "cairo", "alexandria", "giza", "mena")):
                return term
        return ""

    @staticmethod
    def _normalize_date(raw: str) -> str:
        """Convert any feed date string to ISO YYYY-MM-DD. Empty on failure."""
        if not raw:
            return ""
        raw = raw.strip()
        # feedparser usually gives us a struct_time we can't see here,
        # so try common string formats.
        for fmt in (
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
        return ""

    @staticmethod
    def _within_window(iso_date: str, days: int) -> bool:
        try:
            d = datetime.date.fromisoformat(iso_date)
        except ValueError:
            return False
        today = datetime.date.today()
        return (today - d).days <= days and d <= today

    @staticmethod
    def _is_egypt_civil(job: dict) -> bool:
        loc = (job.get("location") or "").lower()
        title = (job.get("title") or "").lower()
        desc = (job.get("description_full") or "").lower()
        blob = f"{loc} {title} {desc}"

        egypt_terms = ("egypt", "cairo", "alexandria", "giza", "mena",
                       "egyptian", "north africa")
        civil_terms = (
            "civil", "structural", "geotechnical", "transportation",
            "water resources", "construction", "site engineer",
            "quantity survey", "infrastructure", "highway", "bridge",
            "sanitation", "watsan", "wash", "shelter", "urban planning",
            "roads", "dams", "foundations", "architect", "building",
            "engineer",  # loose match: UN posts often say "Engineer"
        )

        has_egypt = any(w in blob for w in egypt_terms)
        has_civil = any(w in blob for w in civil_terms)
        return has_egypt and has_civil


engine = Engine()
