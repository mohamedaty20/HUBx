# engine.py
# Self-learning loop that EXPANDS its own topic list.
# Every cycle generates a topic, then asks Gemini for 3 new sub-topics
# that get queued for future cycles.

import asyncio
import json
import logging
from typing import Optional

from sources import (SEED_TOPICS, LEARNING_INTERVAL_SECONDS,
                     REFINE_EVERY_N_CYCLES, SUGGESTIONS_PER_CYCLE,
                     MAX_KNOWLEDGE_ITEMS,
                     SUGGEST_TOPICS_SYSTEM, SUGGEST_TOPICS_USER)
from db import (upsert_knowledge, set_refined,
                oldest_knowledge_for_refinement, log_learning_run,
                knowledge_stats, add_pending_topic, pop_pending_topic,
                pending_count)
import gemini as gemini_mod

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


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
        s = knowledge_stats()
        if s["total"] >= MAX_KNOWLEDGE_ITEMS:
            self.last_debug = f"cap reached ({MAX_KNOWLEDGE_ITEMS} topics)"
            return

        # Refine every Nth cycle, otherwise generate
        if self.cycles_completed % REFINE_EVERY_N_CYCLES == 3:
            await self._refine_one()
        else:
            await self._generate_one()

    async def _generate_one(self):
        if self.paused:
            return

        # Prefer the pending queue (AI-generated topics) over seed topics.
        pending = pop_pending_topic()
        if pending:
            topic, category = pending
            source = "ai"
        else:
            topic, category = SEED_TOPICS[self._topic_index % len(SEED_TOPICS)]
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
            self.last_debug = f"generated [{source}]: {topic}"
            # Ask Gemini for new sub-topics to grow the queue
            await self._expand_topics(topic, category)
        else:
            err = gemini_mod.last_error or "empty response"
            log_learning_run(self.cycles_completed, topic, 0, 0, 1, error=err)
            self.last_debug = f"no content for: {topic} | {err}"

    async def _expand_topics(self, parent_topic, parent_category):
        """Ask Gemini for SUGGESTIONS_PER_CYCLE new sub-topics."""
        if self.paused:
            return
        if pending_count() > 200:
            return  # queue already large enough

        self.gemini_calls += 1
        user = SUGGEST_TOPICS_USER.format(
            topic=parent_topic, category=parent_category,
            n=SUGGESTIONS_PER_CYCLE)
        raw = await gemini_mod._call(
            f"{SUGGEST_TOPICS_SYSTEM.format(n=SUGGESTIONS_PER_CYCLE)}"
            f"\n\n---\n\n{user}",
            json_mode=True,
        )

        if self.paused:
            return

        if not raw:
            return
        try:
            data = json.loads(raw)
        except Exception:
            return
        subtopics = data.get("subtopics", []) if isinstance(data, dict) else []
        added = 0
        for item in subtopics[:SUGGESTIONS_PER_CYCLE]:
            if not isinstance(item, dict):
                continue
            t = (item.get("topic") or "").strip()
            c = (item.get("category") or parent_category).strip()
            if add_pending_topic(t, c, source="ai", parent_topic=parent_topic):
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
            set_refined(kid, improved, confidence=0.8)
            log_learning_run(self.cycles_completed, topic, 0, 1, 1)
            self.last_debug = f"refined: {topic} (v{version + 1})"
        else:
            err = gemini_mod.last_error or "no change"
            log_learning_run(self.cycles_completed, topic, 0, 0, 1, error=err)
            self.last_debug = f"no refinement for: {topic} | {err}"

    def stats(self) -> dict:
        s = knowledge_stats()
        return {
            "cycles": self.cycles_completed,
            "gemini_calls": self.gemini_calls,
            "knowledge_total": s["total"],
            "knowledge_refined": s["refined"],
            "pending_topics": s.get("pending", 0),
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_debug": self.last_debug,
        }


engine = Engine()
