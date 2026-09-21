# engine.py
# Self-learning loop. Every LEARNING_INTERVAL_SECONDS the engine either
# generates new knowledge for the next seed topic or refines the oldest
# existing knowledge item. All AI calls are guarded by the pause flag.

import asyncio
import logging
from typing import Optional

from sources import SEED_TOPICS, LEARNING_INTERVAL_SECONDS, \
    REFINE_EVERY_N_CYCLES
from db import (upsert_knowledge, set_refined,
                oldest_knowledge_for_refinement, log_learning_run,
                knowledge_stats)

# Import the module, not the name, so gemini.last_error is read live.
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
            logger.info("Learning loop cancelled.")
            raise

    async def _cycle(self):
        # Alternate between generating new knowledge and refining old.
        if self.cycles_completed % REFINE_EVERY_N_CYCLES == 1:
            await self._refine_one()
        else:
            await self._generate_one()

    async def _generate_one(self):
        if self.paused:
            return
        topic, category = SEED_TOPICS[self._topic_index % len(SEED_TOPICS)]
        self._topic_index += 1

        if self.paused:
            return
        self.gemini_calls += 1
        content = await gemini_mod.generate_knowledge(topic, category)

        if self.paused:
            logger.info("Discarding knowledge response - paused mid-call.")
            return

        if content:
            upsert_knowledge(topic, category, content, confidence=0.6)
            log_learning_run(self.cycles_completed, topic, 1, 0, 1)
            self.last_debug = f"generated: {topic}"
        else:
            err = gemini_mod.last_error or "empty response"
            log_learning_run(self.cycles_completed, topic, 0, 0, 1,
                             error=err)
            self.last_debug = f"no content for: {topic} | gemini: {err}"

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
            logger.info("Discarding refinement - paused mid-call.")
            return

        if improved and improved != existing:
            set_refined(kid, improved, confidence=0.8)
            log_learning_run(self.cycles_completed, topic, 0, 1, 1)
            self.last_debug = f"refined: {topic} (v{version + 1})"
        else:
            err = gemini_mod.last_error or "no change"
            log_learning_run(self.cycles_completed, topic, 0, 0, 1,
                             error=err)
            self.last_debug = f"no refinement for: {topic} | gemini: {err}"

    def stats(self) -> dict:
        s = knowledge_stats()
        return {
            "cycles": self.cycles_completed,
            "gemini_calls": self.gemini_calls,
            "knowledge_total": s["total"],
            "knowledge_refined": s["refined"],
            "last_status": self.last_status,
            "last_error": self.last_error,
            "last_debug": self.last_debug,
        }


engine = Engine()
