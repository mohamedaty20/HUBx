# engine.py
# Dual learning loop: knowledge topics + Egyptian site templates.
# Version replacement: when a refined version is produced, the old row is
# deleted from the database and only the new version remains.

import asyncio
import json
import re
import logging
from typing import Optional

from sources import (SEED_TOPICS, LEARNING_INTERVAL_SECONDS,
                     REFINE_EVERY_N_CYCLES, SUGGESTIONS_PER_CYCLE,
                     MAX_KNOWLEDGE_ITEMS,
                     SUGGEST_TOPICS_SYSTEM, SUGGEST_TOPICS_USER,
                     SEED_TEMPLATES, TEMPLATE_INTERVAL_SECONDS,
                     MAX_TEMPLATES,
                     SUGGEST_TEMPLATES_SYSTEM, SUGGEST_TEMPLATES_USER)
from db import (upsert_knowledge, replace_knowledge_with_refined,
                oldest_knowledge_for_refinement, log_learning_run,
                knowledge_stats, add_pending_topic, pop_pending_topic,
                pending_count,
                upsert_template, replace_template_with_refined,
                oldest_template_for_refinement, log_template_run,
                template_stats, add_pending_template,
                pop_pending_template, pending_template_count)
import gemini as gemini_mod

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ALLOWED_CATEGORIES = {
    "concrete", "steel", "soil", "water", "roads",
    "quality_management", "egyptian_codes", "safety", "surveying",
}

ALLOWED_TEMPLATE_CATEGORIES = {
    "administrative", "quality", "safety", "technical",
    "financial", "legal", "handover",
}


def _safe_json(raw):
    if not raw:
        return {}
    s = str(raw).strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        v = json.loads(s)
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except Exception:
                pass
        if isinstance(v, dict):
            return v
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        try:
            v = json.loads(m.group(0))
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except Exception:
                    pass
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    fixed = s.replace('\\"', '"')
    m = re.search(r"\{.*\}", fixed, re.S)
    if m:
        try:
            v = json.loads(m.group(0))
            if isinstance(v, dict):
                return v
        except Exception:
            pass
    return {}


def _extract_subtopics(data):
    if not isinstance(data, dict):
        return []
    items = (data.get("subtopics") or data.get("sub_topics")
             or data.get("topics") or data.get("items") or [])
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if isinstance(it, dict):
            t = (it.get("topic") or it.get("title") or "").strip()
            c = (it.get("category") or "").strip().lower()
        elif isinstance(it, str):
            t = it.strip()
            c = ""
        else:
            continue
        if t:
            out.append((t, c))
    return out


def _extract_templates(data):
    if not isinstance(data, dict):
        return []
    items = (data.get("templates") or data.get("items") or [])
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except Exception:
            items = []
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if isinstance(it, dict):
            n = (it.get("name") or it.get("title") or "").strip()
            c = (it.get("category") or "").strip().lower()
        elif isinstance(it, str):
            n = it.strip()
            c = ""
        else:
            continue
        if n:
            out.append((n, c))
    return out


class Engine:
    def __init__(self):
        self.running = False
        self.paused = True
        self.cycles_completed = 0
        self.gemini_calls = 0
        self.last_status = "idle"
        self.last_error = ""
        self.last_debug = "waiting for first cycle"
        self._topic_index = 0
        self._template_index = 0
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
                    logger.exception("Learning cycle failed")

                for _ in range(LEARNING_INTERVAL_SECONDS):
                    if self.paused:
                        return
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise

    async def _cycle(self):
        # Alternate: knowledge, template, knowledge, template...
        if self.cycles_completed % 2 == 0:
            await self._knowledge_cycle()
        else:
            await self._template_cycle()

    # ------------------------------------------------------------------
    # Knowledge cycle
    # ------------------------------------------------------------------

    async def _knowledge_cycle(self):
        s = knowledge_stats()
        if s["total"] >= MAX_KNOWLEDGE_ITEMS:
            self.last_debug = f"knowledge cap reached"
            return
        if self.cycles_completed % REFINE_EVERY_N_CYCLES == 3:
            await self._refine_one()
        else:
            await self._generate_one()

    async def _generate_one(self):
        if self.paused:
            return
        pending = pop_pending_topic()
        if pending:
            topic, category = pending
            source = "ai"
        else:
            topic, category = SEED_TOPICS[
                self._topic_index % len(SEED_TOPICS)]
            self._topic_index += 1
            source = "seed"

        if self.paused:
            return
        self.gemini_calls += 1
        content = await gemini_mod.generate_knowledge(topic, category)
        if self.paused:
            return

        if content:
            upsert_knowledge(topic, category, content, confidence=0.6)
            log_learning_run(self.cycles_completed, topic, 1, 0, 1)
            self.last_debug = f"[K] generated [{source}]: {topic}"
            try:
                await self._expand_topics(topic, category)
            except Exception as e:
                self.last_debug += f" | expand err: {e}"
        else:
            err = gemini_mod.last_error or "empty response"
            log_learning_run(self.cycles_completed, topic, 0, 0, 1,
                             error=err)
            self.last_debug = f"[K] no content for: {topic} | {err}"

    async def _expand_topics(self, parent_topic, parent_category):
        if self.paused or pending_count() > 200:
            return
        self.gemini_calls += 1
        user = SUGGEST_TOPICS_USER.format(
            topic=parent_topic, category=parent_category,
            n=SUGGESTIONS_PER_CYCLE)
        raw = await gemini_mod._call(
            f"{SUGGEST_TOPICS_SYSTEM}\n\n---\n\n{user}", json_mode=True)
        if self.paused or not raw:
            return
        data = _safe_json(raw)
        items = _extract_subtopics(data)
        added = 0
        for t, c in items[:SUGGESTIONS_PER_CYCLE]:
            if c not in ALLOWED_CATEGORIES:
                c = parent_category
            if add_pending_topic(t, c, source="ai",
                                 parent_topic=parent_topic):
                added += 1
        if added:
            self.last_debug += f" | +{added} queued"

    async def _refine_one(self):
        if self.paused:
            return
        rows = oldest_knowledge_for_refinement(1)
        if not rows:
            await self._generate_one()
            return
        row = rows[0]
        kid, topic, category, content, refined, version = row
        existing = refined or content
        if not existing:
            return
        if self.paused:
            return
        self.gemini_calls += 1
        improved = await gemini_mod.refine_knowledge(topic, existing)
        if self.paused:
            return
        if improved and improved != existing:
            # Version replacement: old row deleted, new row inserted.
            replace_knowledge_with_refined(kid, improved)
            log_learning_run(self.cycles_completed, topic, 0, 1, 1)
            self.last_debug = f"[K] refined v{version + 1}: {topic}"
        else:
            err = gemini_mod.last_error or "no change"
            log_learning_run(self.cycles_completed, topic, 0, 0, 1,
                             error=err)
            self.last_debug = f"[K] no refinement: {topic} | {err}"

    # ------------------------------------------------------------------
    # Template cycle
    # ------------------------------------------------------------------

    async def _template_cycle(self):
        s = template_stats()
        if s["total"] >= MAX_TEMPLATES:
            self.last_debug = "[T] template cap reached"
            return
        if self.cycles_completed % REFINE_EVERY_N_CYCLES == 1:
            await self._refine_template()
        else:
            await self._generate_template()

    async def _generate_template(self):
        if self.paused:
            return
        pending = pop_pending_template()
        if pending:
            name, category = pending
            source = "ai"
        else:
            name, category = SEED_TEMPLATES[
                self._template_index % len(SEED_TEMPLATES)]
            self._template_index += 1
            source = "seed"

        if self.paused:
            return
        self.gemini_calls += 1
        content = await gemini_mod.generate_template(name, category)
        if self.paused:
            return
        if content:
            upsert_template(name, category, content, confidence=0.6)
            log_template_run(self.cycles_completed, name, 1, 0, 1)
            self.last_debug = f"[T] generated [{source}]: {name}"
            try:
                await self._expand_templates(name, category)
            except Exception as e:
                self.last_debug += f" | expand err: {e}"
        else:
            err = gemini_mod.last_error or "empty response"
            log_template_run(self.cycles_completed, name, 0, 0, 1,
                             error=err)
            self.last_debug = f"[T] no content: {name} | {err}"

    async def _expand_templates(self, parent_name, parent_category):
        if self.paused or pending_template_count() > 100:
            return
        self.gemini_calls += 1
        user = SUGGEST_TEMPLATES_USER.format(
            name=parent_name, category=parent_category,
            n=SUGGESTIONS_PER_CYCLE)
        raw = await gemini_mod._call(
            f"{SUGGEST_TEMPLATES_SYSTEM}\n\n---\n\n{user}", json_mode=True)
        if self.paused or not raw:
            return
        data = _safe_json(raw)
        items = _extract_templates(data)
        added = 0
        for n, c in items[:SUGGESTIONS_PER_CYCLE]:
            if c not in ALLOWED_TEMPLATE_CATEGORIES:
                c = parent_category
            if add_pending_template(n, c, source="ai",
                                    parent_name=parent_name):
                added += 1
        if added:
            self.last_debug += f" | +{added} templates queued"

    async def _refine_template(self):
        if self.paused:
            return
        rows = oldest_template_for_refinement(1)
        if not rows:
            await self._generate_template()
            return
        row = rows[0]
        tid, name, category, content, refined, version = row
        existing = refined or content
        if not existing:
            return
        if self.paused:
            return
        self.gemini_calls += 1
        improved = await gemini_mod.refine_template(name, existing)
        if self.paused:
            return
        if improved and improved != existing:
            replace_template_with_refined(tid, improved)
            log_template_run(self.cycles_completed, name, 0, 1, 1)
            self.last_debug = f"[T] refined v{version + 1}: {name}"
        else:
            err = gemini_mod.last_error or "no change"
            log_template_run(self.cycles_completed, name, 0, 0, 1,
                             error=err)
            self.last_debug = f"[T] no refinement: {name} | {err}"

    def stats(self) -> dict:
        ks = knowledge_stats()
        ts = template_stats()
        return {
            "cycles": self.cycles_completed,
            "gemini_calls": self.gemini_calls,
            "knowledge_total": ks["total"],
            "knowledge_refined": ks["refined"],
            "pending_topics": ks.get("pending", 0),
            "template_total": ts["total"],
            "template_refined": ts["refined"],
            "pending_templates": ts.get("pending", 0),
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_debug": self.last_debug,
        }


engine = Engine()
