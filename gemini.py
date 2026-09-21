# gemini.py
# Gemini called ONLY for (a) strategy refinement, (b) result scoring.
# JSON-only output with retry on malformed JSON.

import os
import json
import asyncio
import logging

import google.generativeai as genai

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


STRATEGY_REFINEMENT_PROMPT = """
You are a search-strategy refiner for a civil-engineering job board in Egypt.

Today's date: {today}

Current strategy:
{current_strategy}

Recent failures (last {n_failures}):
{failures}

Allowed domains and tiers:
{allowed_domains}

Rules you MUST follow:
- Require at least ONE change vs the current strategy.
- Retire any query that returned zero relevant results twice.
- Never suggest scraping sites whose ToS forbids it.
- Focus on Egypt + civil engineering (structural, geotechnical,
  transportation, water resources, construction management).
- Return ONLY valid JSON, no markdown.

Output JSON schema:
{{
  "queries": ["query1", "query2"],
  "sources": ["domain1", "domain2"],
  "reasoning": "one paragraph explaining changes",
  "confidence": 0.0
}}
"""

RESULT_SCORING_PROMPT = """
Score this job posting for relevance and quality.

Job title: {title}
Company: {company}
Location: {location}
Description: {description}

Return ONLY valid JSON:
{{
  "relevance_score": 0.0,
  "quality_score": 0.0,
  "reason": "short explanation"
}}
"""


async def _call_gemini_json(prompt: str, max_retries: int = 3) -> dict:
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set - returning empty result.")
        return {}

    model = genai.GenerativeModel(GEMINI_MODEL)
    last_raw = ""
    for attempt in range(max_retries):
        try:
            resp = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7 if attempt == 0 else 1.0,
                    response_mime_type="application/json",
                ),
            )
            last_raw = (resp.text or "").strip()
            if last_raw.startswith("```"):
                last_raw = last_raw.split("\n", 1)[-1].rsplit("```", 1)[0]
            return json.loads(last_raw)
        except json.JSONDecodeError:
            logger.warning("Malformed JSON attempt %d: %.200s",
                           attempt + 1, last_raw)
            await asyncio.sleep(1.0 * (attempt + 1))
        except Exception as e:
            logger.error("Gemini call failed: %s", e)
            await asyncio.sleep(2.0)
    return {}


async def refine_strategy(today: str, current_strategy: dict,
                          failures: list, allowed_domains: dict) -> dict:
    prompt = STRATEGY_REFINEMENT_PROMPT.format(
        today=today,
        current_strategy=json.dumps(current_strategy, indent=2),
        n_failures=len(failures),
        failures=json.dumps(
            [{"query": f[0], "domain": f[1], "type": f[2], "msg": f[3]}
             for f in failures], indent=2),
        allowed_domains=json.dumps(allowed_domains, indent=2),
    )
    return await _call_gemini_json(prompt)


async def score_result(job: dict) -> dict:
    prompt = RESULT_SCORING_PROMPT.format(
        title=job.get("title", ""),
        company=job.get("company", ""),
        location=job.get("location", ""),
        description=(job.get("description_full") or "")[:2000],
    )
    return await _call_gemini_json(prompt)
