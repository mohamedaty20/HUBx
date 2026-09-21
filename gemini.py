# gemini.py
# Gemini API wrapper with model fallback and error surfacing.

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

# Fallback chain - tries each until one works.
_PREFERRED = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
MODEL_CANDIDATES = [
    _PREFERRED,
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash",
    "gemini-1.5-flash",
]
# Deduplicate while preserving order.
_seen = set()
MODEL_CANDIDATES = [m for m in MODEL_CANDIDATES
                    if not (m in _seen or _seen.add(m))]

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Public: last error observed by any call, so UI can show it.
last_error = ""
_working_model: str | None = None

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


def _pick_model():
    """Return the first model that previously worked, else try all."""
    if _working_model:
        return [_working_model]
    return MODEL_CANDIDATES


async def _try_text(model_name: str, system_prompt: str,
                    user_prompt: str) -> str:
    model = genai.GenerativeModel(
        model_name, system_instruction=system_prompt)
    resp = await asyncio.to_thread(
        model.generate_content,
        user_prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.6),
    )
    return (resp.text or "").strip()


async def _call_text(system_prompt: str, user_prompt: str) -> str:
    global last_error, _working_model
    if not GEMINI_API_KEY:
        last_error = "GEMINI_API_KEY not set"
        return ""

    for model_name in _pick_model():
        for attempt in range(2):
            await _throttle()
            try:
                text = await _try_text(model_name, system_prompt, user_prompt)
                if text:
                    _working_model = model_name
                    last_error = ""
                    return text
                last_error = f"{model_name}: empty response"
            except Exception as e:
                last_error = f"{model_name}: {type(e).__name__}: {e}"
                logger.warning("Gemini call failed on %s: %s",
                               model_name, e)
                await asyncio.sleep(2 ** attempt)
    logger.error("All Gemini models failed. last_error=%s", last_error)
    return ""


async def _try_json(model_name: str, system_prompt: str,
                    user_prompt: str) -> dict:
    import json
    model = genai.GenerativeModel(
        model_name, system_instruction=system_prompt)
    resp = await asyncio.to_thread(
        model.generate_content,
        user_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.4,
            response_mime_type="application/json",
        ),
    )
    raw = (resp.text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    return json.loads(raw)


async def _call_json(system_prompt: str, user_prompt: str) -> dict:
    global last_error, _working_model
    if not GEMINI_API_KEY:
        last_error = "GEMINI_API_KEY not set"
        return {}

    for model_name in _pick_model():
        for attempt in range(2):
            await _throttle()
            try:
                result = await _try_json(model_name, system_prompt, user_prompt)
                if isinstance(result, dict):
                    _working_model = model_name
                    last_error = ""
                    return result
            except Exception as e:
                last_error = f"{model_name}: {type(e).__name__}: {e}"
                logger.warning("Gemini JSON call failed on %s: %s",
                               model_name, e)
                await asyncio.sleep(2 ** attempt)
    return {}


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

async def generate_knowledge(topic: str, category: str) -> str:
    user = KNOWLEDGE_USER_TEMPLATE.format(topic=topic, category=category)
    return await _call_text(KNOWLEDGE_SYSTEM_PROMPT, user)


async def refine_knowledge(topic: str, existing: str) -> str:
    user = REFINE_USER_TEMPLATE.format(topic=topic, content=existing[:4000])
    return await _call_text(REFINE_SYSTEM_PROMPT, user)


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


async def ocr_image(path: str) -> str:
    global last_error, _working_model
    if not GEMINI_API_KEY:
        return ""
    try:
        from PIL import Image
        img = Image.open(path)
        for model_name in _pick_model():
            await _throttle()
            try:
                model = genai.GenerativeModel(model_name)
                resp = await asyncio.to_thread(
                    model.generate_content,
                    ["Transcribe every word of text in this image. "
                     "Preserve line breaks. Return plain text only.", img],
                )
                text = (resp.text or "").strip()
                if text:
                    _working_model = model_name
                    return text
            except Exception as e:
                last_error = f"OCR {model_name}: {e}"
                continue
    except Exception as e:
        last_error = f"OCR load: {e}"
    return ""
