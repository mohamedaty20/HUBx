# engine.py
# v9: phase expansion appends only the new section. On failure, bump
#     phase_ts so the same item isn't retried immediately.

from __future__ import annotations
import asyncio
import inspect
import json as _json
import traceback

from gemini import (
    generate_knowledge, refine_knowledge,
    generate_template, refine_template,
    expand_phase,
    suggest_subtopics, suggest_subtemplates,
)

import db as _db

from sources import (
    LEARNING_INTERVAL_SECONDS, TEMPLATE_INTERVAL_SECONDS,
    SUGGESTIONS_PER_CYCLE, SEED_TOPICS, SEED_TEMPLATES,
)

PAUSED_KEY = "engine_paused_by_user"
MAX_PHASE_DEFAULT = 8
PHASE_MIN_AGE_SECONDS = 14400   # 4 hours between phase advances of same item


def _get_max_phase():
    try:
        v = _db.get_app_state("max_phase", str(MAX_PHASE_DEFAULT))
        n = int(v)
        return max(1, min(8, n))
    except Exception:
        return MAX_PHASE_DEFAULT


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
        return _db.get_knowledge_by_topic(topic)
    except Exception:
        return None


def _existing_template(name):
    try:
        return _db.get_template_by_name(name)
    except Exception:
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
            max_phase = _get_max_phase()

            run_k = mode in ("knowledge", "both")
            run_t = mode in ("templates", "both")

            if run_k:
                if await self._advance_knowledge(max_phase):
                    self.ai_calls = self.gemini_calls
                    return
            if run_t:
                if await self._advance_template(max_phase):
                    self.ai_calls = self.gemini_calls
                    return

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

    # ---------------- phase advancement ----------------
    async def _advance_knowledge(self, max_phase):
        try:
            row = _db.phaseable_knowledge(max_phase, PHASE_MIN_AGE_SECONDS)
        except Exception as e:
            print(f"[engine] phaseable_knowledge failed: {e}")
            return False
        if not row:
            return False

        kid, topic, category, content, phase = row
        target = int(phase) + 1
        if target > max_phase:
            return False

        self.last_debug = f"phase {phase}->{target}: {topic}"
        new_section = await expand_phase(topic, category,
                                         content or "", phase, target)
        self.gemini_calls += 1

        # ALWAYS bump phase_ts so we don't retry the same item for 4h.
        if not new_section or len(new_section.strip()) < 200:
            # Failed or too short. Bump timestamp but don't advance.
            try:
                _db.advance_knowledge_phase(kid, content or "", phase)
            except Exception:
                pass
            self.last_debug = f"phase expand failed: {topic}"
            _db.log_learning_run(self.cycles, topic, 0, 0, 1,
                                 f"phase->{target} failed")
            return True

        # Append the new section to existing content.
        combined = (content or "").rstrip() + "\n\n\n" + new_section.strip()
        try:
            _db.advance_knowledge_phase(kid, combined, target)
        except Exception as e:
            print(f"[engine] advance_knowledge_phase failed: {e}")
            return True

        _db.log_learning_run(self.cycles, topic, 0, 1, 1, f"phase->{target}")
        self.last_debug = f"advanced to phase {target}: {topic}"
        return True

    async def _advance_template(self, max_phase):
        try:
            row = _db.phaseable_template(max_phase, PHASE_MIN_AGE_SECONDS)
        except Exception as e:
            print(f"[engine] phaseable_template failed: {e}")
            return False
        if not row:
            return False

        tid, name, category, content, phase = row
        target = int(phase) + 1
        if target > max_phase:
            return False

        self.last_debug = f"phase {phase}->{target}: {name}"
        new_section = await expand_phase(name, category,
                                         content or "", phase, target)
        self.gemini_calls += 1

        if not new_section or len(new_section.strip()) < 200:
            try:
                _db.advance_template_phase(tid, content or "", phase)
            except Exception:
                pass
            self.last_debug = f"phase expand failed: {name}"
            _db.log_template_run(self.cycles, name, 0, 0, 1,
                                 f"phase->{target} failed")
            return True

        combined = (content or "").rstrip() + "\n\n\n" + new_section.strip()
        try:
            _db.advance_template_phase(tid, combined, target)
        except Exception as e:
            print(f"[engine] advance_template_phase failed: {e}")
            return True

        _db.log_template_run(self.cycles, name, 0, 1, 1, f"phase->{target}")
        self.last_debug = f"advanced to phase {target}: {name}"
        return True

    # ---------------- generate new ----------------
    async def _knowledge_step(self, focus_cats):
        focus_cats = focus_cats or set()
        topic = category = None

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
            if _existing_knowledge(t):
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
                    if not _existing_knowledge(t):
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
            if _existing_template(t):
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
                    t = subs[0]
                    if not _existing_template(t):
                        name, category = t, "quality"
            except Exception as e:
                print(f"[engine] fresh template suggestion failed: {e}")

        if not name:
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
                if _db.add_pending_template(s, category, "ai", name):
                    added += 1
            self.last_debug = f"generated: {name} (+{added} queued)"
        except Exception as e:
            print(f"[engine] suggest_subtemplates failed: {e}")

    def stats(self) -> dict:
        kb_total = kb_refined = kb_pending = 0
        kb_avg_phase = 1.0
        kb_advanced = 0
        tpl_total = tpl_pending = 0
        tpl_avg_phase = 1.0
        tpl_advanced = 0
        try:
            ks = _db.knowledge_stats()
            if isinstance(ks, dict):
                kb_total = ks.get("total", 0)
                kb_refined = ks.get("refined", 0)
                kb_pending = ks.get("pending", 0)
                kb_avg_phase = ks.get("avg_phase", 1.0)
                kb_advanced = ks.get("advanced", 0)
        except Exception:
            pass
        try:
            ts = _db.template_stats()
            if isinstance(ts, dict):
                tpl_total = ts.get("total", 0)
                tpl_pending = ts.get("pending", 0)
                tpl_avg_phase = ts.get("avg_phase", 1.0)
                tpl_advanced = ts.get("advanced", 0)
        except Exception:
            pass

        return {
            "cycles": self.cycles,
            "gemini_calls": self.gemini_calls,
            "knowledge_total": kb_total,
            "knowledge_refined": kb_refined,
            "knowledge_avg_phase": kb_avg_phase,
            "knowledge_advanced": kb_advanced,
            "template_total": tpl_total,
            "template_avg_phase": tpl_avg_phase,
            "template_advanced": tpl_advanced,
            "pending_topics": kb_pending,
            "pending_templates": tpl_pending,
            "max_phase": _get_max_phase(),
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
