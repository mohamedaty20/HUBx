# gemini.py
# Gemini wrapper with sanitizer, quota-aware pacing,
# template generation, and AI-powered knowledge search.

import os
import re
import json
import asyncio
import logging
import time

import google.generativeai as genai

from prompts import (
    KNOWLEDGE_SYSTEM_PROMPT, KNOWLEDGE_USER_TEMPLATE,
    REFINE_SYSTEM_PROMPT, REFINE_USER_TEMPLATE,
    CHECKER_SYSTEM_PROMPT, CHECKER_USER_TEMPLATE,
    TEMPLATE_SYSTEM_PROMPT, TEMPLATE_USER_TEMPLATE,
)

from db import (check_and_increment_gemini_usage,
                gemini_usage_stats, purge_old_gemini_usage)

logger = logging.getLogger(__name__)

# ==================================================================
# HARDCODED MODEL. Edit this line to change model.
# ==================================================================
MODEL = "gemini-3.5-flash-lite"
# ==================================================================

# Daily + hourly soft caps enforced by db.check_and_increment_gemini_usage.
# Free tier is 500 RPD; leave headroom for manual AI-search / doc-check.
GEMINI_DAY_LIMIT = 400
GEMINI_HOUR_LIMIT = 30

# In-memory block so the engine loop does not spin the DB every 20s
# while we are over the cap. Cleared when the timer expires.
_quota_block_until = 0.0
_QUOTA_BLOCK_SECONDS = 300

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

last_error = ""

_rate_lock = asyncio.Lock()
_last_call_time = 0.0
MIN_CALL_GAP = 2.0

# Purge old usage rows once at import time (safe, small).
try:
    purge_old_gemini_usage(keep_days=3)
except Exception:
    pass


# ---------------------------------------------------------------
# LaTeX sanitizer
# ---------------------------------------------------------------
_LATEX_SIMPLE = [
    (r"\\times\b", "×"), (r"\\cdot\b", "·"), (r"\\div\b", "÷"),
    (r"\\pm\b", "±"), (r"\\mp\b", "∓"), (r"\\geq\b", "≥"),
    (r"\\ge\b", "≥"), (r"\\leq\b", "≤"), (r"\\le\b", "≤"),
    (r"\\neq\b", "≠"), (r"\\ne\b", "≠"), (r"\\approx\b", "≈"),
    (r"\\propto\b", "∝"), (r"\\infty\b", "∞"),
    (r"\\rightarrow\b", "→"), (r"\\to\b", "→"),
    (r"\\leftarrow\b", "←"), (r"\\degree\b", "°"),
    (r"\\circ\b", "°"), (r"\\left\b", ""), (r"\\right\b", ""),
    (r"\\displaystyle\b", ""), (r"\\quad\b", " "),
    (r"\\qquad\b", "  "), (r"\\,", " "), (r"\\;", " "),
    (r"\\!", ""), (r"\\%", "%"), (r"\\&", "&"),
    (r"\\#", "#"), (r"\\_", "_"), (r"\\\$", "$"),
]


def sanitize_text(s):
    """Convert any LaTeX / math markup to plain readable text."""
    if not s:
        return s
    s = str(s)
    s = re.sub(r"\\text(?:bf|it|rm|sf|tt)?\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\math(?:bf|it|rm|sf|tt)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", s)
    s = re.sub(r"\\sqrt\{([^{}]*)\}", r"√(\1)", s)
    s = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", s)
    s = re.sub(r"_\{([^{}]*)\}", r"_\1", s)
    s = re.sub(r"\^([0-9A-Za-z])", r"^\1", s)
    for pat, rep in _LATEX_SIMPLE:
        s = re.sub(pat, rep, s)
    s = s.replace("$$", " ").replace("$", "")
    s = re.sub(r"\\[A-Za-z]+\b", "", s).replace("\\", "")
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


def _parse_retry_seconds(err_str, fallback):
    try:
        m = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", err_str)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    try:
        m = re.search(r"'seconds':\s*(\d+)", err_str)
        if m:
            return float(m.group(1))
    except Exception:
        pass
    return float(fallback)


def _is_quota_error(err_str):
    s = (err_str or "").lower()
    return ("429" in s or "quota" in s or "resourceexhausted" in s
            or "rate limit" in s or "exceeded" in s)


async def _call(prompt, json_mode=False, max_tokens=8192, max_retries=6):
    global last_error, _quota_block_until

    if not GEMINI_API_KEY:
        last_error = "GEMINI_API_KEY not set"
        return ""

    # -- soft block set after a previous cap hit -------------------
    now_m = time.monotonic()
    if now_m < _quota_block_until:
        left = int(_quota_block_until - now_m)
        last_error = f"{MODEL}: quota cap reached, paused {left}s"
        return ""

    kwargs = {"temperature": 0.4 if json_mode else 0.7,
              "max_output_tokens": max_tokens}
    if json_mode:
        kwargs["response_mime_type"] = "application/json"

    model = genai.GenerativeModel(MODEL)
    for attempt in range(max_retries):
        # quota check BEFORE every attempt (counts retries too)
        allowed = check_and_increment_gemini_usage(
            day_limit=GEMINI_DAY_LIMIT,
            hour_limit=GEMINI_HOUR_LIMIT,
        )
        if not allowed:
            _quota_block_until = time.monotonic() + _QUOTA_BLOCK_SECONDS
            last_error = (f"{MODEL}: daily/hourly cap reached "
                          f"({GEMINI_DAY_LIMIT}/day, "
                          f"{GEMINI_HOUR_LIMIT}/hour), paused "
                          f"{_QUOTA_BLOCK_SECONDS}s")
            logger.warning(last_error)
            return ""

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
            err_str = f"{type(e).__name__}: {e}"
            if _is_quota_error(err_str):
                # Gemini itself says quota — back off hard.
                backoff = 5 * (2 ** attempt)
                wait_s = _parse_retry_seconds(str(e), backoff)
                wait_s = min(max(wait_s, 5.0), 180.0)
                last_error = (f"{MODEL}: Gemini 429, waiting {wait_s:.0f}s "
                              f"(attempt {attempt + 1}/{max_retries})")
                logger.warning(last_error)
                await asyncio.sleep(wait_s)
                continue
            last_error = f"{MODEL}: {err_str}"
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
                       json_mode=False, max_tokens=8192)


async def refine_knowledge(topic, existing):
    user = REFINE_USER_TEMPLATE.format(topic=topic, content=existing[:6000])
    return await _call(f"{REFINE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=8192)


async def generate_template(name, category):
    user = TEMPLATE_USER_TEMPLATE.format(name=name, category=category)
    return await _call(f"{TEMPLATE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=8192)


async def refine_template(name, existing):
    return await _call(
        "Improve the following construction template. Add missing fields, "
        "more detail in each section, more sample values, more common "
        "mistakes. Keep the same structure. Return only the improved "
        "template, plain text, no LaTeX.\n\n---\n\n"
        f"Template: {name}\n\n{existing[:6000]}",
        json_mode=False, max_tokens=8192)


async def check_document(filename, file_type, text):
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


async def ai_search(question, knowledge_context):
    """
    Answer a user question by reading the supplied knowledge context.
    Returns a plain-text answer or "" on failure.
    """
    prompt = (
        "You are a senior Egyptian civil quality engineer. Answer the "
        "user's question using ONLY the knowledge base excerpts below. "
        "If the excerpts do not contain the answer, say so clearly and "
        "suggest which topic would help.\n\n"
        "ANSWER RULES:\n"
        "- 300-600 words.\n"
        "- Plain English, no LaTeX, no dollar signs.\n"
        "- Use markdown headings and bullet lists.\n"
        "- Cite the topic name in brackets when you quote an excerpt, "
        "e.g. [Hot weather concreting].\n"
        "- End with a '## Related topics' list of 3-5 topics from the "
        "excerpts that the user should read next.\n\n"
        f"=== KNOWLEDGE BASE EXCERPTS ===\n{knowledge_context}\n\n"
        f"=== USER QUESTION ===\n{question}\n"
    )
    return await _call(prompt, json_mode=False, max_tokens=4096)


async def ocr_image(path):
    global last_error
    if not GEMINI_API_KEY:
        return ""
    allowed = check_and_increment_gemini_usage(
        day_limit=GEMINI_DAY_LIMIT, hour_limit=GEMINI_HOUR_LIMIT)
    if not allowed:
        last_error = "quota cap reached (OCR skipped)"
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
