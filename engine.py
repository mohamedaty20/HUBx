# engine.py
# v13: Auto phase advancement when no new templates available.
#      Keeps v1->v2->v3 workflow, replaces old versions in DB.

from __future__ import annotations
import asyncio
import json as _json
import traceback

from gemini import (
    generate_knowledge, refine_knowledge,
    generate_template, refine_template,
    suggest_subtopics, suggest_subtemplates,
    expand_phase,
)

import db as _db
import db

from sources import (
    LEARNING_INTERVAL_SECONDS, TEMPLATE_INTERVAL_SECONDS,
    SUGGESTIONS_PER_CYCLE, SEED_TOPICS, SEED_TEMPLATES,
)

PAUSED_KEY = "engine_paused_by_user"
DEDUP_EVERY_N_CYCLES = 20


def _read_focus_state():
    try:
        mode = _db.get_app_state("focus_mode", "both") or "both"
        raw = _db.get_app_state("focus_categories", "") or ""
        cats = []
        if raw:
            try:
                parsed = _json.loads(raw)
                if isinstance(parsed, list):
                    cats = [str(x) for x in parsed]
            except Exception:
                cats = []
        return mode, set(cats)
    except Exception:
        return "both", set()


def _existing_knowledge(topic):
    try:
        row = _db.get_knowledge_by_topic(topic)
        if row:
            return row
        if db.knowledge_canonical_exists(topic):
            return True
    except Exception:
        pass
    return None


def _existing_template(name):
    try:
        row = _db.get_template_by_name(name)
        if row:
            return row
        if db.template_canonical_exists(name):
            return True
    except Exception:
        pass
    return None


class Engine:
    def __init__(self):
        self.running = False
        self.paused = True
        self.cycles = 0
        self.cycles_completed = 0
        self.gemini_calls = 0
        self.ai_calls = 0
        self.last_status = "idle"
        self.last_error = ""
        self.last_debug = ""
        self._task = None
        self._wake = asyncio.Event()
        self._lock = asyncio.Lock()
        self._k_idx = 0
        self._t_idx = 0

    async def start(self, by_user=True):
        if self.running:
            return
        self.running = True
        self.paused = False
        self.last_status = "running"
        self.last_error = ""
        self.last_debug = "started"
        if by_user:
            _db.set_app_state(PAUSED_KEY, "0")
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        else:
            self._wake.set()

    async def pause(self):
        self.running = False
        self.paused = True
        self.last_status = "paused"
        self.last_debug = "paused"
        _db.set_app_state(PAUSED_KEY, "1")
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
                    self.cycles_completed = self.cycles
                    if self.cycles % DEDUP_EVERY_N_CYCLES == 0:
                        try:
                            res = await asyncio.to_thread(
                                db.deduplicate_all)
                            self.last_debug = f"dedup: {res}"
                        except Exception as e:
                            print(f"[engine] dedup failed: {e}")
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = f"{type(e).__name__}: {e}"
                    self.last_debug = f"cycle error: {e}"
                    traceback.print_exc()

                if not self.running:
                    break
                interval = min(float(LEARNING_INTERVAL_SECONDS),
                               float(TEMPLATE_INTERVAL_SECONDS))
                elapsed = asyncio.get_event_loop().time() - t0
                wait = max(0.0, interval - elapsed)
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
            self.last_status = "running"
            mode, focus_cats = _read_focus_state()
            run_k = mode in ("knowledge", "both")
            run_t = mode in ("templates", "both")

            if run_k:
                try:
                    await self._knowledge_step(focus_cats)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = f"knowledge: {e}"
                    self.last_debug = f"knowledge error: {e}"

            if run_t:
                try:
                    await self._template_step(focus_cats)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = f"templates: {e}"
                    self.last_debug = f"templates error: {e}"

            self.ai_calls = self.gemini_calls

    async def _knowledge_step(self, focus_cats):
        focus_cats = focus_cats or set()
        topic = category = None

        existing_topics = set()
        try:
            rows = await asyncio.to_thread(
                lambda: _db.get_all_knowledge(limit=10000))
            for r in rows:
                c = db._canonical(r[1])
                if c:
                    existing_topics.add(c)
        except Exception:
            pass

        def _exists(t):
            if t in existing_topics:
                return True
            c = db._canonical(t)
            return bool(c and c in existing_topics)

        for _ in range(20):
            item = None
            try:
                item = _db.pop_pending_topic()
            except Exception:
                item = None

            if item:
                t, c = item[0], item[1]
            else:
                if not SEED_TOPICS:
                    break
                t, c = SEED_TOPICS[self._k_idx % len(SEED_TOPICS)]
                self._k_idx += 1

            if focus_cats and c not in focus_cats:
                continue
            if _exists(t):
                continue
            topic, category = t, c
            break

        if not topic:
            queue_empty = True
            try:
                queue_empty = (_db.pending_count() == 0)
            except Exception:
                queue_empty = True
            if not queue_empty:
                self.last_debug = "no matching topics in queue"
                return
            try:
                subs = await suggest_subtopics(
                    "Egyptian civil quality engineering",
                    "quality_management", n=1)
                self.gemini_calls += 1
                if subs:
                    t = subs[0]
                    if not _exists(t):
                        topic, category = t, "quality_management"
            except Exception as e:
                print(f"[engine] fresh suggestion failed: {e}")

        if not topic:
            self.last_debug = "no new knowledge topics available"
            return

        self.last_debug = f"generating: {topic}"
        content = await generate_knowledge(topic, category)
        self.gemini_calls += 1
        if not content:
            self.last_debug = f"failed: {topic}"
            _db.log_learning_run(self.cycles, topic, 0, 0, 1, "empty")
            return

        _db.upsert_knowledge(topic, category, content, confidence=0.7)
        self.last_debug = f"generated: {topic}"
        _db.log_learning_run(self.cycles, topic, 1, 0, 1, "")

        try:
            subs = await suggest_subtopics(
                topic, category, n=int(SUGGESTIONS_PER_CYCLE or 2))
            self.gemini_calls += 1
            added = 0
            for s in subs:
                if _db.add_pending_topic(s, category, "ai", topic):
                    added += 1
            self.last_debug = f"generated: {topic} (+{added} queued)"
        except Exception as e:
            print(f"[engine] suggest_subtopics failed: {e}")

    async def _template_step(self, focus_cats):
        focus_cats = focus_cats or set()
        name = category = None

        existing_templates = set()
        try:
            rows = await asyncio.to_thread(
                lambda: _db.get_all_templates(limit=10000))
            for r in rows:
                c = db._canonical(r[1])
                if c:
                    existing_templates.add(c)
        except Exception:
            pass

        def _exists(nm):
            if nm in existing_templates:
                return True
            c = db._canonical(nm)
            return bool(c and c in existing_templates)

        for _ in range(20):
            item = None
            try:
                item = _db.pop_pending_template()
            except Exception:
                item = None

            if item:
                t, c = item[0], item[1]
            else:
                if not SEED_TEMPLATES:
                    break
                seed = SEED_TEMPLATES[self._t_idx % len(SEED_TEMPLATES)]
                self._t_idx += 1
                if isinstance(seed, (list, tuple)) and len(seed) >= 2:
                    t, c = seed[0], seed[1]
                else:
                    t, c = str(seed), "administrative"

            if focus_cats and c not in focus_cats:
                continue
            if _exists(t):
                continue
            name, category = t, c
            break

        if not name:
            queue_empty = True
            try:
                queue_empty = (_db.pending_template_count() == 0)
            except Exception:
                queue_empty = True
            if not queue_empty:
                self.last_debug = "no matching templates in queue"
                return
            try:
                subs = await suggest_subtemplates(
                    "Egyptian construction site template", "quality", n=1)
                self.gemini_calls += 1
                if subs:
                    t = subs[0].get("name", "")
                    c = subs[0].get("category", "quality")
                    if not _exists(t):
                        name, category = t, c
            except Exception as e:
                print(f"[engine] fresh template suggestion failed: {e}")

        if not name:
            # No new templates available. Try to advance an existing one.
            advanced = await self._advance_template_phase()
            if advanced:
                return
            self.last_debug = "no new templates available"
            return

        self.last_debug = f"generating template: {name}"
        content = await generate_template(name, category)
        self.gemini_calls += 1
        if not content:
            self.last_debug = f"failed: {name}"
            _db.log_template_run(self.cycles, name, 0, 0, "empty")
            return

        _db.upsert_template(name, category, content, confidence=0.7)
        self.last_debug = f"generated template: {name}"
        _db.log_template_run(self.cycles, name, 1, 0, "")

        try:
            subs = await suggest_subtemplates(
                name, category, n=int(SUGGESTIONS_PER_CYCLE or 2))
            self.gemini_calls += 1
            added = 0
            for s in subs:
                s_name = s.get("name", "")
                s_cat = s.get("category", category)
                if _db.add_pending_template(s_name, s_cat, "ai", name):
                    added += 1
            self.last_debug = f"generated: {name} (+{added} queued)"
        except Exception as e:
            print(f"[engine] suggest_subtemplates failed: {e}")

    async def _advance_template_phase(self):
        """Pick the oldest template below max_phase and upgrade it.
        This replaces v1 with v2 (bumps version) in the DB."""
        try:
            max_phase = int(_db.get_app_state("max_phase", "8") or "8")
        except Exception:
            max_phase = 8
        if max_phase <= 1:
            return False
        try:
            rows = await asyncio.to_thread(
                lambda: _db.get_all_templates(limit=5000))
        except Exception:
            return False
        candidates = []
        for r in rows:
            # r = (id, name, category, content, refined, version,
            #      confidence, updated_at)
            tid, tname, tcat = r[0], r[1], r[2]
            content = r[4] or r[3] or ""
            version = r[5] or 1
            # we store phase in version-1 terms: v2 = Phase 2, etc.
            current_phase = version if version >= 1 else 1
            if current_phase >= max_phase:
                continue
            if not content.strip():
                continue
            candidates.append((tid, tname, tcat, content, current_phase))
        if not candidates:
            return False
        # Pick the least recently updated / oldest version
        candidates.sort(key=lambda x: x[4])  # lowest phase first
        tid, tname, tcat, old_content, cur_phase = candidates[0]
        target_phase = cur_phase + 1
        self.last_debug = (f"advancing {tname[:40]} "
                           f"(v{cur_phase} → v{target_phase})")
        try:
            new_section = await expand_phase(
                tname, tcat, old_content, cur_phase, target_phase)
            self.gemini_calls += 1
        except Exception as e:
            print(f"[engine] expand_phase failed: {e}")
            return False
        if not new_section:
            self.last_debug = f"expand failed: {tname}"
            return False
        # Append the new phase to the existing content
        merged = old_content.rstrip() + "\n\n---\n\n" + new_section.strip()
        try:
            _db.upsert_template(tname, tcat, merged, confidence=0.7)
            _db.log_template_run(
                self.cycles, f"{tname} (v{cur_phase}->v{target_phase})",
                1, 1, "")
            self.last_debug = (f"advanced: {tname[:40]} "
                               f"(v{cur_phase}->v{target_phase})")
        except Exception as e:
            print(f"[engine] upsert after advance failed: {e}")
            return False
        return True

    def stats(self) -> dict:
        kb_total = kb_refined = kb_pending = 0
        tpl_total = tpl_pending = 0
        try:
            ks = _db.knowledge_stats()
            if isinstance(ks, dict):
                kb_total = ks.get("total", 0)
                kb_refined = ks.get("refined", 0)
                kb_pending = ks.get("pending", 0)
        except Exception:
            pass
        try:
            ts = _db.template_stats()
            if isinstance(ts, dict):
                tpl_total = ts.get("total", 0)
                tpl_pending = ts.get("pending", 0)
        except Exception:
            pass

        return {
            "cycles": self.cycles,
            "gemini_calls": self.gemini_calls,
            "knowledge_total": kb_total,
            "knowledge_refined": kb_refined,
            "template_total": tpl_total,
            "pending_topics": kb_pending,
            "pending_templates": tpl_pending,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_debug": self.last_debug,
        }


engine = Engine()


async def auto_start_if_needed():
    try:
        paused_flag = _db.get_app_state(PAUSED_KEY, "0")
    except Exception:
        paused_flag = "0"
    if str(paused_flag) == "1":
        engine.paused = True
        engine.running = False
        engine.last_status = "paused"
        engine.last_debug = "auto-start skipped (user paused)"
        print("[engine] auto-start skipped")
        return
    print("[engine] auto-starting")
    await engine.start(by_user=False)
