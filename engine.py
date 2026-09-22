# engine.py
# v4: real expansion loop — pop pending first, suggest sub-topics after
#     each generation. Refine only unverified/unflagged rows.

from __future__ import annotations
import asyncio
import inspect
import traceback

from gemini import (
    generate_knowledge, refine_knowledge,
    generate_template, refine_template,
    suggest_subtopics, suggest_subtemplates,
)

import db as _db

from sources import (
    LEARNING_INTERVAL_SECONDS, TEMPLATE_INTERVAL_SECONDS,
    REFINE_EVERY_N_CYCLES, SUGGESTIONS_PER_CYCLE,
    MAX_KNOWLEDGE_ITEMS, MAX_TEMPLATES,
    SEED_TOPICS, SEED_TEMPLATES,
)

try:
    from state import STATE
except Exception:
    class _S:
        focus = "both"
        @property
        def run_knowledge(self): return self.focus in ("knowledge", "both")
        @property
        def run_templates(self): return self.focus in ("templates", "both")
    STATE = _S()


PAUSED_KEY = "engine_paused_by_user"


# ==================================================================
# DB adapters
# ==================================================================
def _find(*names):
    for n in names:
        fn = getattr(_db, n, None)
        if callable(fn):
            return fn
    return None

_SAVE_KNOWLEDGE = _find("save_knowledge", "add_knowledge",
                        "insert_knowledge", "upsert_knowledge")
_SAVE_TEMPLATE  = _find("save_template", "add_template",
                        "insert_template", "upsert_template")
_SAVE_LRUN      = _find("save_learning_run", "add_learning_run",
                        "log_learning_run", "insert_learning_run")
_SAVE_TRUN      = _find("save_template_run", "add_template_run",
                        "log_template_run", "insert_template_run")
_GET_KNOWLEDGE_BY_TOPIC = _find("get_knowledge_by_topic")
_GET_TEMPLATE_BY_NAME   = _find("get_template_by_name")
_POP_TOPIC      = _find("pop_pending_topic")
_POP_TEMPLATE   = _find("pop_pending_template")
_ADD_TOPIC      = _find("add_pending_topic")
_ADD_TEMPLATE   = _find("add_pending_template")
_OLDEST_KN      = _find("oldest_unverified_knowledge")
_OLDEST_TPL     = _find("oldest_unverified_template")


def _call_adapt(fn, *args, **kwargs):
    if not fn:
        return None
    if args:
        try:
            return fn(*args)
        except TypeError:
            pass
        except Exception as e:
            print(f"[db] {getattr(fn, '__name__', fn)} (positional) failed: {e}")
            return None
    try:
        return fn(**kwargs)
    except TypeError:
        pass
    except Exception as e:
        print(f"[db] {getattr(fn, '__name__', fn)} (kwargs) failed: {e}")
        return None
    try:
        sig = inspect.signature(fn)
        filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return fn(**filtered)
    except Exception as e:
        print(f"[db] {getattr(fn, '__name__', fn)} (filtered) failed: {e}")
        return None


def _save_knowledge(topic, category, content,
                    version=1, confidence=0.7, parent_id=None):
    if not _SAVE_KNOWLEDGE:
        print("[engine] db has no save_knowledge")
        return False
    _call_adapt(_SAVE_KNOWLEDGE, topic, category, content,
                topic=topic, category=category, name=topic, title=topic,
                content=content, body=content, text=content,
                markdown=content, version=version,
                confidence=confidence, parent_id=parent_id)
    return True


def _save_template(name, category, content, version=1, confidence=0.7):
    if not _SAVE_TEMPLATE:
        print("[engine] db has no save_template")
        return False
    _call_adapt(_SAVE_TEMPLATE, name, category, content,
                name=name, topic=name, title=name, category=category,
                content=content, body=content, text=content,
                markdown=content, version=version, confidence=confidence)
    return True


def _save_lrun(cycle, topic, added, refined, calls, error=""):
    if _SAVE_LRUN:
        _call_adapt(_SAVE_LRUN, cycle, topic, added, refined, calls, error,
                    cycle=cycle, topic=topic, added=added,
                    refined=refined, calls=calls, error=error)


def _save_trun(cycle, name, added, refined, error=""):
    if _SAVE_TRUN:
        _call_adapt(_SAVE_TRUN, cycle, name, added, refined, error,
                    cycle=cycle, name=name, added=added,
                    refined=refined, error=error)


def _existing_knowledge(topic):
    if not _GET_KNOWLEDGE_BY_TOPIC:
        return None
    try:
        return _GET_KNOWLEDGE_BY_TOPIC(topic)
    except Exception:
        return None


def _existing_template(name):
    if not _GET_TEMPLATE_BY_NAME:
        return None
    try:
        return _GET_TEMPLATE_BY_NAME(name)
    except Exception:
        return None


# ==================================================================
# Engine
# ==================================================================
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

            if STATE.run_knowledge:
                try:
                    await self._knowledge_step()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = f"knowledge: {e}"
                    self.last_debug = f"knowledge error: {e}"
                    print(f"[engine] knowledge step failed: {e}")

            if STATE.run_templates:
                try:
                    await self._template_step()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = f"templates: {e}"
                    self.last_debug = f"templates error: {e}"
                    print(f"[engine] template step failed: {e}")

            self.ai_calls = self.gemini_calls

    # -------- knowledge --------
    async def _knowledge_step(self):
        # 1. Try pending queue
        item = None
        if _POP_TOPIC:
            try:
                item = _POP_TOPIC()
            except Exception:
                item = None

        if item:
            topic, category = item[0], item[1]
            source = "pending"
        else:
            # fall back to seeds
            if not SEED_TOPICS:
                return
            topic, category = SEED_TOPICS[self._k_idx % len(SEED_TOPICS)]
            self._k_idx += 1
            source = "seed"

        existing = _existing_knowledge(topic)

        # Skip already-verified and NOT flagged
        if existing:
            try:
                verified = existing[9] if len(existing) > 9 else 0
                flagged = existing[10] if len(existing) > 10 else 0
            except Exception:
                verified, flagged = 0, 0
            if verified and not flagged:
                self.last_debug = f"skipped verified: {topic}"
                return

        if existing:
            # refine
            body = existing[4] or existing[3] or ""
            self.last_debug = f"refining: {topic}"
            new_body = await refine_knowledge(topic, body)
            self.gemini_calls += 1
            if new_body:
                ver = (existing[5] or 1) + 1
                conf = existing[6] or 0.7
                _save_knowledge(topic, category, new_body,
                                version=ver, confidence=conf)
                self.last_debug = f"refined: {topic}"
                _save_lrun(self.cycles, topic, 0, 1, 1, "")
            else:
                _save_lrun(self.cycles, topic, 0, 0, 1, "refine empty")
            return

        # generate new
        self.last_debug = f"generating: {topic}"
        content = await generate_knowledge(topic, category)
        self.gemini_calls += 1
        if not content:
            self.last_debug = f"empty: {topic}"
            _save_lrun(self.cycles, topic, 0, 0, 1, "gemini empty")
            return

        _save_knowledge(topic, category, content,
                        version=1, confidence=0.7)
        self.last_debug = f"generated: {topic}"
        _save_lrun(self.cycles, topic, 1, 0, 1, "")

        # expand: ask for sub-topics
        try:
            subs = await suggest_subtopics(topic, category,
                                           n=int(SUGGESTIONS_PER_CYCLE or 3))
            self.gemini_calls += 1
            added = 0
            if _ADD_TOPIC:
                for s in subs:
                    if _ADD_TOPIC(s, category, "ai", topic):
                        added += 1
            self.last_debug = f"generated: {topic} (+{added} queued)"
        except Exception as e:
            print(f"[engine] suggest_subtopics failed: {e}")

    # -------- templates --------
    async def _template_step(self):
        item = None
        if _POP_TEMPLATE:
            try:
                item = _POP_TEMPLATE()
            except Exception:
                item = None

        if item:
            name, category = item[0], item[1]
        else:
            if not SEED_TEMPLATES:
                return
            seed = SEED_TEMPLATES[self._t_idx % len(SEED_TEMPLATES)]
            self._t_idx += 1
            if isinstance(seed, (list, tuple)) and len(seed) >= 2:
                name, category = seed[0], seed[1]
            else:
                name, category = str(seed), "administrative"

        existing = _existing_template(name)

        if existing:
            try:
                verified = existing[9] if len(existing) > 9 else 0
                flagged = existing[10] if len(existing) > 10 else 0
            except Exception:
                verified, flagged = 0, 0
            if verified and not flagged:
                self.last_debug = f"skipped verified: {name}"
                return

        if existing:
            body = existing[4] or existing[3] or ""
            self.last_debug = f"refining template: {name}"
            new_body = await refine_template(name, body)
            self.gemini_calls += 1
            if new_body:
                ver = (existing[5] or 1) + 1
                conf = existing[6] or 0.7
                _save_template(name, category, new_body,
                               version=ver, confidence=conf)
                self.last_debug = f"refined template: {name}"
                _save_trun(self.cycles, name, 0, 1, "")
            else:
                _save_trun(self.cycles, name, 0, 0, "refine empty")
            return

        self.last_debug = f"generating template: {name}"
        content = await generate_template(name, category)
        self.gemini_calls += 1
        if not content:
            self.last_debug = f"empty template: {name}"
            _save_trun(self.cycles, name, 0, 0, "gemini empty")
            return

        _save_template(name, category, content,
                       version=1, confidence=0.7)
        self.last_debug = f"generated template: {name}"
        _save_trun(self.cycles, name, 1, 0, "")

        try:
            subs = await suggest_subtemplates(name, category,
                                              n=int(SUGGESTIONS_PER_CYCLE or 3))
            self.gemini_calls += 1
            added = 0
            if _ADD_TEMPLATE:
                for s in subs:
                    if _ADD_TEMPLATE(s, category, "ai", name):
                        added += 1
            self.last_debug = f"generated template: {name} (+{added} queued)"
        except Exception as e:
            print(f"[engine] suggest_subtemplates failed: {e}")

    def stats(self) -> dict:
        kb_total = kb_refined = kb_pending = 0
        tpl_total = tpl_pending = 0
        try:
            ks = _db.knowledge_stats() if hasattr(_db, "knowledge_stats") else {}
            if isinstance(ks, dict):
                kb_total = ks.get("total", 0)
                kb_refined = ks.get("refined", 0)
                kb_pending = ks.get("pending", 0)
        except Exception:
            pass
        try:
            ts = _db.template_stats() if hasattr(_db, "template_stats") else {}
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
        engine.last_debug = "auto-start skipped (paused by user)"
        print("[engine] auto-start skipped — user previously paused")
        return
    print("[engine] auto-starting on boot")
    await engine.start(by_user=False)
