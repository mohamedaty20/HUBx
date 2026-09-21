# gemini.py
# Gemini wrapper. Model is HARDCODED. All text is sanitized (no LaTeX).

import os
import re
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
# HARDCODED MODEL. Edit this line to change model. Env var is ignored.
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


# ---------------------------------------------------------------
# LaTeX sanitizer
# ---------------------------------------------------------------

_LATEX_SIMPLE = [
    (r"\\times\b", "×"),
    (r"\\cdot\b", "·"),
    (r"\\div\b", "÷"),
    (r"\\pm\b", "±"),
    (r"\\mp\b", "∓"),
    (r"\\geq\b", "≥"),
    (r"\\ge\b", "≥"),
    (r"\\leq\b", "≤"),
    (r"\\le\b", "≤"),
    (r"\\neq\b", "≠"),
    (r"\\ne\b", "≠"),
    (r"\\approx\b", "≈"),
    (r"\\sim\b", "~"),
    (r"\\propto\b", "∝"),
    (r"\\infty\b", "∞"),
    (r"\\rightarrow\b", "→"),
    (r"\\to\b", "→"),
    (r"\\leftarrow\b", "←"),
    (r"\\degree\b", "°"),
    (r"\\circ\b", "°"),
    (r"\\left\b", ""),
    (r"\\right\b", ""),
    (r"\\displaystyle\b", ""),
    (r"\\quad\b", " "),
    (r"\\qquad\b", "  "),
    (r"\\,", " "),
    (r"\\;", " "),
    (r"\\!", ""),
    (r"\\%", "%"),
    (r"\\&", "&"),
    (r"\\#", "#"),
    (r"\\_", "_"),
    (r"\\\$", "$"),
]


def sanitize_text(s):
    """Convert any LaTeX / math markup to plain readable text."""
    if not s:
        return s
    s = str(s)

    # \text{...}, \mathrm{...}, \mathbf{...}, \mathit{...} -> inner
    s = re.sub(r"\\text(?:bf|it|rm|sf|tt)?\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\math(?:bf|it|rm|sf|tt)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", s)

    # \frac{a}{b} -> (a)/(b)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)

    # \sqrt{x} -> √(x)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)

    # x^{...} -> x^(...)  ; x_{...} -> x_(...)
    s = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", s)
    s = re.sub(r"_\{([^{}]*)\}", r"_\1", s)
    s = re.sub(r"\^([0-9A-Za-z])", r"^\1", s)

    # Simple replacements
    for pat, rep in _LATEX_SIMPLE:
        s = re.sub(pat, rep, s)

    # Remove math delimiters
    s = s.replace("$$", " ")
    s = s.replace("$", "")

    # Any leftover \command
    s = re.sub(r"\\[A-Za-z]+\b", "", s)
    s = s.replace("\\", "")

    # Collapse whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ---------------------------------------------------------------
# Low-level call
# ---------------------------------------------------------------

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
                return sanitize_text(text)
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

    # Sanitize every string field
    result["summary"] = sanitize_text(result.get("summary", ""))
    issues = result.get("issues", []) or []
    for it in issues:
        if not isinstance(it, dict):
            continue
        for k in ("location", "problem", "fix", "reference", "severity"):
            if k in it:
                it[k] = sanitize_text(it[k])
    result["issues"] = issues
    result.setdefault("score", 0.0)
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
        return sanitize_text(_extract_text(resp))
    except Exception as e:
        last_error = f"OCR: {e}"
        return ""
