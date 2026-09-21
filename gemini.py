# gemini.py
# Model name is HARDCODED. Env var is ignored (it kept getting misconfigured).
# To change the model, edit the MODEL constant below.

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

# ==================================================================
# HARDCODED MODEL. Edit this line if you want a different model.
# ==================================================================
MODEL = "gemini-3.5-flash-lite"
# ==================================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

last_error = ""

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


def _extract_text(resp):
    try:
        t = resp.text
        if t:
            return t.strip()
    except Exception:
        pass
    try:
        parts = resp.candidates[0].content.parts
        joined = "".join(getattr(p, "text", "") or "" for p in parts)
        if joined.strip():
            return joined.strip()
    except Exception:
        pass
    return ""


async def _call(prompt, json_mode=False):
    global last_error
    if not GEMINI_API_KEY:
        last_error = "GEMINI_API_KEY not set"
        return ""

    kwargs = {"temperature": 0.4 if json_mode else 0.6}
    if json_mode:
        kwargs["response_mime_type"] = "application/json"

    model = genai.GenerativeModel(MODEL)
    for attempt in range(3):
        await _throttle()
        try:
            resp = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(**kwargs),
            )
            text = _extract_text(resp)
            if text:
                last_error = ""
                return text
            last_error = f"{MODEL}: empty response"
        except Exception as e:
            last_error = f"{MODEL}: {type(e).__name__}: {e}"
            logger.warning("Gemini call failed (attempt %d): %s",
                           attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return ""


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

async def generate_knowledge(topic, category):
    user = KNOWLEDGE_USER_TEMPLATE.format(topic=topic, category=category)
    return await _call(f"{KNOWLEDGE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False)


async def refine_knowledge(topic, existing):
    user = REFINE_USER_TEMPLATE.format(topic=topic, content=existing[:4000])
    return await _call(f"{REFINE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False)


async def check_document(filename, file_type, text):
    import json
    user = CHECKER_USER_TEMPLATE.format(
        filename=filename, file_type=file_type, text=text[:12000])
    raw = await _call(f"{CHECKER_SYSTEM_PROMPT}\n\n---\n\n{user}",
                      json_mode=True)
    if not raw:
        return {}
    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(raw)
    except Exception:
        return {}
    if not isinstance(result, dict):
        return {}
    result.setdefault("score", 0.0)
    result.setdefault("summary", "")
    result.setdefault("issues", [])
    return result


async def ocr_image(path):
    global last_error
    if not GEMINI_API_KEY:
        return ""
    try:
        from PIL import Image
        img = Image.open(path)
        await _throttle()
        model = genai.GenerativeModel(MODEL)
        resp = await asyncio.to_thread(
            model.generate_content,
            ["Transcribe every word of text in this image. "
             "Preserve line breaks. Return plain text only.", img],
        )
        return _extract_text(resp)
    except Exception as e:
        last_error = f"OCR: {e}"
        return ""
