# engine.py
"""
Self-learning loop.
v3: auto-start on boot, persisted pause state in DB.
"""

from __future__ import annotations
import asyncio
import inspect
import traceback

from gemini import (
    generate_knowledge, refine_knowledge,
    generate_template, refine_template,
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
_GET_KNOWLEDGE_BY_TOPIC = _find("get_knowledge_by_topic",
                                "find_knowledge_by_topic",
                                "get_knowledge")
_GET_TEMPLATE_BY_NAME   = _find("get_template_by_name",
                                "find_template_by_name",
                                "get_template")


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
        print("[engine] db has no save_knowledge — knowledge NOT stored")
        return False
    _call_adapt(
        _SAVE_KNOWLEDGE,
        topic, category, content,
        topic=topic, category=category, name=topic, title=topic,
        content=content, body=content, text=content, markdown=content,
        version=version, confidence=confidence, parent_id=parent_id,
    )
    return True


def _save_template(name, category, content,
                   version=1, confidence=0.7):
    if not _SAVE_TEMPLATE:
        print("[engine] db has no save_template — template NOT stored")
        return False
    _call_adapt(
        _SAVE_TEMPLATE,
        name, category, content,
        name=name, topic=name, title=name,
        category=category,
        content=content, body=content, text=content, markdown=content,
        version=version, confidence=confidence,
    )
    return True


def _save_lrun(cycle, topic, added, refined, calls, error=""):
    if not _SAVE_LRUN:
        return
    _call_adapt(
        _SAVE_LRUN,
        cycle, topic, added, refined, calls, error,
        cycle=cycle, topic=topic, added=added, refined=refined,
        calls=calls, error=error,
    )


def _save_trun(cycle, name, added, refined, error=""):
    if not _SAVE_TRUN:
        return
    _call_adapt(
        _SAVE_TRUN,
        cycle, name, added, refined, error,
        cycle=cycle, name=name, added=added, refined=refined, error=error,
    )


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
            # user explicitly pressed Start -> clear the persisted pause
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
        # persist so next boot does NOT auto-start
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

    async def _knowledge_step(self):
        if not SEED_TOPICS:
            return
        topic, category = SEED_TOPICS[self._k_idx % len(SEED_TOPICS)]
        self._k_idx += 1
        self.last_debug = f"knowledge: {topic}"

        existing = _existing_knowledge(topic)

        if existing:
            body = ""
            try:
                body = existing[4] or existing[3] or ""
            except Exception:
                body = ""
            new_body = await refine_knowledge(topic, body)
            self.gemini_calls += 1
            if new_body:
                ver, conf, pid = 2, 0.7, None
                try:
                    ver = (existing[5] or 1) + 1
                    conf = existing[6] or 0.7
                    pid = existing[0]
                except Exception:
                    pass
                _save_knowledge(topic, category, new_body,
                                version=ver, confidence=conf, parent_id=pid)
                self.last_debug = f"refined: {topic}"
                _save_lrun(self.cycles, topic, 0, 1, 1, "")
            else:
                _save_lrun(self.cycles, topic, 0, 0, 1, "refine empty")
            return

        content = await generate_knowledge(topic, category)
        self.gemini_calls += 1
        if content:
            _save_knowledge(topic, category, content,
                            version=1, confidence=0.7)
            self.last_debug = f"generated: {topic}"
            _save_lrun(self.cycles, topic, 1, 0, 1, "")
        else:
            self.last_debug = f"empty: {topic}"
            _save_lrun(self.cycles, topic, 0, 0, 1, "gemini empty")

    async def _template_step(self):
        if not SEED_TEMPLATES:
            return
        item = SEED_TEMPLATES[self._t_idx % len(SEED_TEMPLATES)]
        self._t_idx += 1
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            name, category = item[0], item[1]
        else:
            name, category = str(item), "administrative"
        self.last_debug = f"template: {name}"

        existing = _existing_template(name)

        if existing:
            body = ""
            try:
                body = existing[4] or existing[3] or ""
            except Exception:
                body = ""
            new_body = await refine_template(name, body)
            self.gemini_calls += 1
            if new_body:
                ver, conf = 2, 0.7
                try:
                    ver = (existing[5] or 1) + 1
                    conf = existing[6] or 0.7
                except Exception:
                    pass
                _save_template(name, category, new_body,
                               version=ver, confidence=conf)
                self.last_debug = f"refined template: {name}"
                _save_trun(self.cycles, name, 0, 1, "")
            else:
                _save_trun(self.cycles, name, 0, 0, "refine empty")
            return

        content = await generate_template(name, category)
        self.gemini_calls += 1
        if content:
            _save_template(name, category, content,
                           version=1, confidence=0.7)
            self.last_debug = f"generated template: {name}"
            _save_trun(self.cycles, name, 1, 0, "")
        else:
            self.last_debug = f"empty template: {name}"
            _save_trun(self.cycles, name, 0, 0, "gemini empty")

    def stats(self) -> dict:
        kb_total = kb_refined = 0
        tpl_total = tpl_pending = 0
        try:
            ks = _db.knowledge_stats() if hasattr(_db, "knowledge_stats") else {}
            if isinstance(ks, dict):
                kb_total = ks.get("total", 0)
                kb_refined = ks.get("refined", 0)
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
            "pending_topics": tpl_pending,
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_debug": self.last_debug,
        }


engine = Engine()


# ==================================================================
# Boot helper
# ==================================================================
async def auto_start_if_needed():
    """Called on app boot. Starts the engine unless the user had paused it."""
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
