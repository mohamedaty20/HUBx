# engine.py
# 70-second loop with pause/start, cancellation, counters.
# Pause is REAL: when paused, no Gemini call is initiated, and any
# in-flight call's response is discarded, not stored.

import asyncio
import datetime
import logging
from typing import Optional

import feedparser

from sources import SOURCES, LIVE_FETCH_URLS, FALLBACK_URLS, get_tier
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
        self.last_debug = ""
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
        strategy = self._ensure_fresh_strategy()
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
                    first_reject = ""

                    for job in all_jobs[:MAX_JOBS_PER_CYCLE]:
                        if self.paused:
                            break
                        iso_date = self._normalize_date(job.get("posted_date"))
                        if not iso_date:
                            if not first_reject:
                                first_reject = (
                                    f"no date: "
                                    f"{(job.get('title') or '')[:40]}"
                                )
                            continue
                        if not self._within_window(iso_date, MAX_AGE_DAYS):
                            if not first_reject:
                                first_reject = (
                                    f"old ({iso_date}): "
                                    f"{(job.get('title') or '')[:40]}"
                                )
                            continue
                        if not self._is_egypt_civil(job):
                            if not first_reject:
                                first_reject = (
                                    f"filter: "
                                    f"{(job.get('title') or '')[:40]}"
                                )
                            continue

                        job["posted_date"] = iso_date
                        job["source_domain"] = domain
                        job["source_tier"] = get_tier(domain)
                        insert_job(job)
                        kept += 1

                    line = (
                        f"{domain}: {len(all_jobs)} entries, "
                        f"{kept - kept_before} kept"
                    )
                    if first_reject:
                        line += f" [1st reject: {first_reject}]"
                    debug_lines.append(line)

                except ComplianceError as e:
                    # Try fallback URLs for this domain
                    fallbacks = FALLBACK_URLS.get(domain, [])
                    recovered = False
                    for fb in fallbacks:
                        if self.paused:
                            break
                        try:
                            text = await safe_fetch(fb)
                            all_jobs = self._parse_feed_or_html(text, domain)
                            kept_before = kept
                            for job in all_jobs[:MAX_JOBS_PER_CYCLE]:
                                iso_date = self._normalize_date(
                                    job.get("posted_date"))
                                if not iso_date:
                                    continue
                                if not self._within_window(
                                        iso_date, MAX_AGE_DAYS):
                                    continue
                                if not self._is_egypt_civil(job):
                                    continue
                                job["posted_date"] = iso_date
                                job["source_domain"] = domain
                                job["source_tier"] = get_tier(domain)
                                insert_job(job)
                                kept += 1
                            debug_lines.append(
                                f"{domain} (fallback): "
                                f"{len(all_jobs)} entries, "
                                f"{kept - kept_before} kept"
                            )
                            recovered = True
                            break
                        except Exception:
                            continue
                    if not recovered:
                        errors += 1
                        debug_lines.append(f"{domain}: {e}")
                        log_failure(strategy_id, "", domain,
                                    "compliance", str(e))

                except Exception as e:
                    errors += 1
                    debug_lines.append(f"{domain}: fetch error - {e}")
                    log_failure(strategy_id, "", domain, "fetch", str(e))

            self.last_debug = " | ".join(debug_lines) or "no sources configured"

            if (self.cycles_completed + 1) % REFINE_EVERY_N == 0 and not self.paused:
                await self._refine(strategy_id, strategy)

        finally:
            finish_run(run_id, fetched, kept, errors)

    # ------------------------------------------------------------------
    # Auto-rebuild the strategy when the DB one is stale
    # ------------------------------------------------------------------

    def _ensure_fresh_strategy(self) -> dict:
        """
        Load the active strategy. If none of its sources exist in
        LIVE_FETCH_URLS, it's stale (built before sources.py was updated)
        so we save a fresh bootstrap and return that instead.
        """
        strategy = get_active_strategy()
        live_keys = set(LIVE_FETCH_URLS.keys())

        if strategy is None or not (set(strategy.get("sources", [])) & live_keys):
            bootstrap_sources = [d for d, t in SOURCES.items() if t in ("A", "B")]
            save_strategy(
                queries=["civil engineer Egypt", "structural engineer Cairo",
                         "WASH engineer Egypt", "infrastructure Egypt"],
                sources=bootstrap_sources,
                reasoning="auto-bootstrap: previous strategy had no live sources",
                confidence=0.5,
            )
            strategy = get_active_strategy()
            self.last_debug = (
                f"rebuilt strategy -> sources: {bootstrap_sources}"
            )
        return strategy

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

        # Safety: never let Gemini introduce domains that aren't live-configurable.
        proposed = result.get("sources", strategy.get("sources", []))
        safe_sources = [d for d in proposed if d in LIVE_FETCH_URLS] or \
                       strategy.get("sources", [])
        save_strategy(
            queries=result.get("queries", strategy.get("queries", [])),
            sources=safe_sources,
            reasoning=result.get("reasoning", ""),
            confidence=float(result.get("confidence", 0.5)),
        )

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_feed_or_html(text: str, domain: str) -> list[dict]:
        jobs = []
        feed = feedparser.parse(text)
        for entry in feed.entries[:100]:
            # Prefer struct_time from feedparser - more reliable than the string
            iso = ""
            for key in ("published_parsed", "updated_parsed"):
                t = entry.get(key)
                if t:
                    try:
                        iso = datetime.date(*t[:3]).isoformat()
                        break
                    except Exception:
                        continue

            jobs.append({
                "title": entry.get("title", ""),
                "company": entry.get("author", "") or
                            Engine._source_name(entry),
                "location": entry.get("location", "") or
                            Engine._location_from_tags(entry),
                "posted_date": iso,
                "url": entry.get("link", ""),
                "description_full": entry.get("summary", ""),
                "recruiter_name": "",
                "recruiter_title": "",
                "recruiter_contact": "",
            })
        return jobs

    @staticmethod
    def _source_name(entry) -> str:
        src = entry.get("source") or {}
        if isinstance(src, dict):
            return src.get("title", "")
        return ""

    @staticmethod
    def _location_from_tags(entry) -> str:
        tags = entry.get("tags", []) or []
        for t in tags:
            term = (t.get("term") or "").strip()
            if any(k in term.lower() for k in (
                    "egypt", "cairo", "alexandria", "giza", "mena")):
                return term
        return ""

    @staticmethod
    def _normalize_date(raw: str) -> str:
        if not raw:
            return ""
        raw = raw.strip()
        if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
            return raw[:10]
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
        blob = " ".join([
            (job.get("location") or "").lower(),
            (job.get("title") or "").lower(),
            (job.get("description_full") or "").lower(),
        ])
        egypt_terms = (
            "egypt", "cairo", "alexandria", "giza", "mena",
            "egyptian", "north africa", "mısır", "misr", "qahira",
        )
        civil_terms = (
            "civil", "structural", "geotechnical", "transportation",
            "water resources", "construction", "site engineer",
            "quantity survey", "infrastructure", "highway", "bridge",
            "sanitation", "watsan", "wash", "shelter", "urban planning",
            "roads", "dams", "foundations", "building", "engineer",
            "architect", "water", "energy", "environment",
        )
        return any(w in blob for w in egypt_terms) and \
               any(w in blob for w in civil_terms)


engine = Engine()
