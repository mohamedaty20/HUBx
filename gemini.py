# gemini.py
# Gemini API wrapper. Two jobs only:
# 1. Generate / refine civil quality knowledge.
# 2. Analyse user-uploaded documents for engineering mistakes.

import os
import asyncio
import logging
import time

import google.generativeai as genai

from prompts import (
    KNOWLEDGE_SYSTEM_PROMPT, KNOWLEDGE_USER_TEMPLATE,
    REFINE_SYSTEM_PROMPT, REFINE_USER_TEMPLATE,
    CHECKER_SYSTEM_PROMPT, CHECKER_USER_TEMPLATE,
)

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

_rate_lock = asyncio.Lock()
_last_call_time = 0.0
MIN_CALL_GAP = 2.0


async def _throttle():
    global _last_call_time
    async with _rate_lock:
        now = time.monotonic()
        wait = MIN_CALL_GAP - (now - _last_call_time)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_call_time = time.monotonic()


async def _call_text(system_prompt: str, user_prompt: str,
                     retries: int = 3) -> str:
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY missing; returning empty text.")
        return ""

    model = genai.GenerativeModel(
        GEMINI_MODEL, system_instruction=system_prompt)
    for attempt in range(retries):
        await _throttle()
        try:
            resp = await asyncio.to_thread(
                model.generate_content,
                user_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.6,
                ),
            )
            return (resp.text or "").strip()
        except Exception as e:
            logger.warning("Gemini text call attempt %d failed: %s",
                           attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return ""


async def _call_json(system_prompt: str, user_prompt: str,
                     retries: int = 3) -> dict:
    if not GEMINI_API_KEY:
        return {}
    model = genai.GenerativeModel(
        GEMINI_MODEL, system_instruction=system_prompt)
    last_raw = ""
    for attempt in range(retries):
        await _throttle()
        try:
            resp = await asyncio.to_thread(
                model.generate_content,
                user_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    response_mime_type="application/json",
                ),
            )
            last_raw = (resp.text or "").strip()
            if last_raw.startswith("```"):
                last_raw = last_raw.split("\n", 1)[-1].rsplit("```", 1)[0]
            import json
            return json.loads(last_raw)
        except Exception as e:
            logger.warning("Gemini JSON call attempt %d failed: %s",
                           attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return {}


# ---------------------------------------------------------------
# Public: knowledge generation / refinement
# ---------------------------------------------------------------

async def generate_knowledge(topic: str, category: str) -> str:
    user = KNOWLEDGE_USER_TEMPLATE.format(topic=topic, category=category)
    return await _call_text(KNOWLEDGE_SYSTEM_PROMPT, user)


async def refine_knowledge(topic: str, existing: str) -> str:
    user = REFINE_USER_TEMPLATE.format(topic=topic, content=existing[:4000])
    return await _call_text(REFINE_SYSTEM_PROMPT, user)


# ---------------------------------------------------------------
# Public: document checking
# ---------------------------------------------------------------

async def check_document(filename: str, file_type: str, text: str) -> dict:
    user = CHECKER_USER_TEMPLATE.format(
        filename=filename, file_type=file_type, text=text[:12000])
    result = await _call_json(CHECKER_SYSTEM_PROMPT, user)
    if not isinstance(result, dict):
        return {}
    result.setdefault("score", 0.0)
    result.setdefault("summary", "")
    result.setdefault("issues", [])
    return result


# ---------------------------------------------------------------
# Public: image OCR via Gemini vision
# ---------------------------------------------------------------

async def ocr_image(path: str) -> str:
    if not GEMINI_API_KEY:
        return ""
    try:
        from PIL import Image
        img = Image.open(path)
        model = genai.GenerativeModel(GEMINI_MODEL)
        await _throttle()
        resp = await asyncio.to_thread(
            model.generate_content,
            ["Transcribe every word of text in this image. "
             "Preserve line breaks. Return plain text only.", img],
        )
        return (resp.text or "").strip()
    except Exception as e:
        logger.error("OCR failed: %s", e)
        return ""
