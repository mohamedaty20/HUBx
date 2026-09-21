# gemini.py
# Gemini wrapper. Validates and cleans the model name, tries fallbacks.

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

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()


def _clean_model(v):
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1].strip()
    # If the value is literally the env var name, it's a config error.
    if v.upper() in ("GEMINI_MODEL", "MODEL", ""):
        return ""
    # Strip a leading "models/" if present.
    if v.startswith("models/"):
        v = v[len("models/"):]
    # Must start with "gemini-"
    if not v.startswith("gemini-"):
        return ""
    return v


_preferred = _clean_model(os.getenv("GEMINI_MODEL", ""))
MODEL_CANDIDATES = []
for m in [_preferred, "gemini-2.0-flash", "gemini-2.0-flash-lite",
          "gemini-2.5-flash", "gemini-1.5-flash"]:
    if m and m not in MODEL_CANDIDATES:
        MODEL_CANDIDATES.append(m)

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

last_error = ""
_working_model = None

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


async def _try_once(model_name, prompt, json_mode):
    kwargs = {"temperature": 0.4 if json_mode else 0.6}
    if json_mode:
        kwargs["response_mime_type"] = "application/json"
    model = genai.GenerativeModel(model_name)
    resp = await asyncio.to_thread(
        model.generate_content,
        prompt,
        generation_config=genai.types.GenerationConfig(**kwargs),
    )
    return _extract_text(resp)


async def _call(prompt, json_mode=False):
    global last_error, _working_model
    if not GEMINI_API_KEY:
        last_error = "GEMINI_API_KEY not set"
        return ""

    models_to_try = [_working_model] if _working_model else MODEL_CANDIDATES

    for model_name in models_to_try:
        for attempt in range(2):
            await _throttle()
            try:
                text = await _try_once(model_name, prompt, json_mode)
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
    logger.error("All models failed. last_error=%s", last_error)
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
    global last_error, _working_model
    if not GEMINI_API_KEY:
        return ""
    try:
        from PIL import Image
        img = Image.open(path)
        models = [_working_model] if _working_model else MODEL_CANDIDATES
        for model_name in models:
            await _throttle()
            try:
                model = genai.GenerativeModel(model_name)
                resp = await asyncio.to_thread(
                    model.generate_content,
                    ["Transcribe every word of text in this image. "
                     "Preserve line breaks. Return plain text only.", img],
                )
                t = _extract_text(resp)
                if t:
                    _working_model = model_name
                    return t
            except Exception as e:
                last_error = f"OCR {model_name}: {e}"
                continue
    except Exception as e:
        last_error = f"OCR load: {e}"
    return ""
