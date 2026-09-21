# gemini.py
# Gemini wrapper. Mirrors the working v1 call pattern:
# one prompt, no system_instruction (that arg breaks on some models).

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

# Public: last error observed by any call.
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


def _extract_text(resp) -> str:
    """Try every known way to pull text out of a Gemini response."""
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


async def _call(prompt: str, json_mode: bool = False) -> str:
    """
    Single low-level call. System + user merged into one prompt.
    Returns raw text, or "" on failure. Sets last_error on failure.
    """
    global last_error
    if not GEMINI_API_KEY:
        last_error = "GEMINI_API_KEY not set"
        return ""

    cfg_kwargs = {"temperature": 0.4 if json_mode else 0.6}
    if json_mode:
        cfg_kwargs["response_mime_type"] = "application/json"

    model = genai.GenerativeModel(GEMINI_MODEL)
    for attempt in range(3):
        await _throttle()
        try:
            resp = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(**cfg_kwargs),
            )
            text = _extract_text(resp)
            if text:
                last_error = ""
                return text

            # Empty response — log why.
            reason = ""
            try:
                if resp.prompt_feedback:
                    reason = f"prompt_feedback={resp.prompt_feedback}"
            except Exception:
                pass
            try:
                if resp.candidates:
                    finish = getattr(resp.candidates[0], "finish_reason", "")
                    reason += f" finish_reason={finish}"
            except Exception:
                pass
            last_error = f"empty response ({reason or 'no detail'})"
            logger.warning("Gemini returned empty. %s", last_error)
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning("Gemini call failed (attempt %d): %s",
                           attempt + 1, e)
            await asyncio.sleep(2 ** attempt)
    return ""


# ---------------------------------------------------------------
# Public API
# ---------------------------------------------------------------

async def generate_knowledge(topic: str, category: str) -> str:
    user = KNOWLEDGE_USER_TEMPLATE.format(topic=topic, category=category)
    prompt = f"{KNOWLEDGE_SYSTEM_PROMPT}\n\n---\n\n{user}"
    return await _call(prompt, json_mode=False)


async def refine_knowledge(topic: str, existing: str) -> str:
    user = REFINE_USER_TEMPLATE.format(topic=topic, content=existing[:4000])
    prompt = f"{REFINE_SYSTEM_PROMPT}\n\n---\n\n{user}"
    return await _call(prompt, json_mode=False)


async def check_document(filename: str, file_type: str, text: str) -> dict:
    import json
    user = CHECKER_USER_TEMPLATE.format(
        filename=filename, file_type=file_type, text=text[:12000])
    prompt = f"{CHECKER_SYSTEM_PROMPT}\n\n---\n\n{user}"
    raw = await _call(prompt, json_mode=True)
    if not raw:
        return {}
    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        result = json.loads(raw)
    except Exception as e:
        last_error_msg = f"JSON parse failed: {e}"
        logger.warning(last_error_msg)
        return {}
    if not isinstance(result, dict):
        return {}
    result.setdefault("score", 0.0)
    result.setdefault("summary", "")
    result.setdefault("issues", [])
    return result


async def ocr_image(path: str) -> str:
    global last_error
    if not GEMINI_API_KEY:
        last_error = "GEMINI_API_KEY not set"
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
        text = _extract_text(resp)
        if text:
            last_error = ""
        return text
    except Exception as e:
        last_error = f"OCR: {e}"
        logger.error("OCR failed: %s", e)
        return ""
