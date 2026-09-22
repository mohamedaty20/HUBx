# gemini.py
# v10: switched from Google Gemini to Groq (Llama 3.3 70B).
#      14,400 free calls/day, no 429 storms.
#      Same public API as before so engine.py and main.py don't change.

import os
import re
import json
import asyncio
import logging
import time
import random

from groq import AsyncGroq

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
MODEL = "openai/gbt-oss-120b"
# Alternative free models on Groq:
#   "llama-3.1-8b-instant"        - faster, smaller, ~15k RPD
#   "mixtral-8x7b-32768"          - longer context
# ==================================================================

GEMINI_DAY_LIMIT = int(os.getenv("GEMINI_DAY_LIMIT", "5000"))
GEMINI_HOUR_LIMIT = int(os.getenv("GEMINI_HOUR_LIMIT", "400"))
_QUOTA_BLOCK_SECONDS = 120

ATTEMPT_TIMEOUT_SECONDS = 120
MIN_CALL_GAP = 2.0

_quota_block_until = 0.0

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

_client = None
if GROQ_API_KEY:
    _client = AsyncGroq(api_key=GROQ_API_KEY)

last_error = ""

_rate_lock = asyncio.Lock()
_last_call_time = 0.0

try:
    purge_old_gemini_usage(keep_days=3)
except Exception:
    pass


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


async def _throttle():
    global _last_call_time
    async with _rate_lock:
        now = time.monotonic()
        wait = MIN_CALL_GAP - (now - _last_call_time)
        if wait > 0:
            wait += random.uniform(0, 0.3)
            await asyncio.sleep(wait)
        _last_call_time = time.monotonic()


def _is_quota_error(err_str):
    s = (err_str or "").lower()
    return ("429" in s or "quota" in s or "rate limit" in s
            or "too many requests" in s or "exceeded" in s)


async def _call(prompt, json_mode=False, max_tokens=3000, max_retries=3):
    global last_error, _quota_block_until

    if not _client:
        last_error = "GROQ_API_KEY not set"
        return ""

    now_m = time.monotonic()
    if now_m < _quota_block_until:
        left = int(_quota_block_until - now_m)
        last_error = f"{MODEL}: paused after 429, {left}s left"
        return ""

    kwargs = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4 if json_mode else 0.7,
        "max_tokens": max_tokens,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(max_retries):
        allowed = check_and_increment_gemini_usage(
            day_limit=GEMINI_DAY_LIMIT,
            hour_limit=GEMINI_HOUR_LIMIT,
        )
        if not allowed:
            _quota_block_until = time.monotonic() + _QUOTA_BLOCK_SECONDS
            last_error = (f"{MODEL}: cap reached "
                          f"({GEMINI_DAY_LIMIT}/day, "
                          f"{GEMINI_HOUR_LIMIT}/hour), paused "
                          f"{_QUOTA_BLOCK_SECONDS}s")
            logger.warning(last_error)
            return ""

        await _throttle()
        try:
            resp = await asyncio.wait_for(
                _client.chat.completions.create(**kwargs),
                timeout=ATTEMPT_TIMEOUT_SECONDS,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                last_error = ""
                return sanitize_text(text)
            last_error = f"{MODEL}: empty response"
        except asyncio.TimeoutError:
            last_error = (f"{MODEL}: attempt {attempt + 1}/{max_retries} "
                          f"timed out after {ATTEMPT_TIMEOUT_SECONDS}s")
            logger.warning(last_error)
            return ""
        except Exception as e:
            err_str = f"{type(e).__name__}: {e}"
            if _is_quota_error(err_str):
                _quota_block_until = time.monotonic() + _QUOTA_BLOCK_SECONDS
                last_error = (f"{MODEL}: 429, paused "
                              f"{_QUOTA_BLOCK_SECONDS}s")
                logger.warning(last_error)
                return ""
            last_error = f"{MODEL}: {err_str}"
            logger.warning("LLM call failed (attempt %d): %s",
                           attempt + 1, e)
            await asyncio.sleep(3 * (attempt + 1))
    return ""


async def generate_knowledge(topic, category):
    user = KNOWLEDGE_USER_TEMPLATE.format(topic=topic, category=category)
    return await _call(f"{KNOWLEDGE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=3000)


async def refine_knowledge(topic, existing):
    user = REFINE_USER_TEMPLATE.format(topic=topic, content=existing[:6000])
    return await _call(f"{REFINE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=3000)


async def generate_template(name, category):
    user = TEMPLATE_USER_TEMPLATE.format(name=name, category=category)
    return await _call(f"{TEMPLATE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=3000)


async def refine_template(name, existing):
    return await _call(
        "Improve the following construction template. Add missing fields, "
        "more detail in each section, more sample values, more common "
        "mistakes. Keep the same structure. Return only the improved "
        "template, plain text, no LaTeX.\n\n---\n\n"
        f"Template: {name}\n\n{existing[:6000]}",
        json_mode=False, max_tokens=3000)


async def suggest_subtopics(parent_topic, category, n=3):
    prompt = (
        "You are a senior Egyptian civil quality engineer building a "
        "self-study knowledge base. Given the parent topic below, propose "
        f"{n} NEW, specific, learnable sub-topics within the same "
        f"category ({category}) that are NOT the same as the parent and "
        "NOT generic. Each should be a concrete topic an engineer would "
        "search for, 6-14 words long, mentioning the code or method where "
        "relevant.\n\n"
        'Return ONLY a JSON object: {"subtopics": ["...", "..."]}\n\n'
        f"Parent topic: {parent_topic}\n"
    )
    raw = await _call(prompt, json_mode=True, max_tokens=512)
    if not raw:
        return []
    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(raw)
        if isinstance(data, dict):
            for key in ("subtopics", "topics", "items"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
        if isinstance(data, list):
            return [sanitize_text(str(x)).strip() for x in data
                    if isinstance(x, (str, int)) and str(x).strip()]
    except Exception:
        pass
    return []


async def suggest_subtemplates(parent_name, category, n=3):
    prompt = (
        "You are a senior Egyptian civil quality engineer building a "
        "library of Egyptian construction site paper templates. Given the "
        f"parent template below, propose {n} NEW, specific template names "
        f"within the same category ({category}) that are NOT duplicates and "
        "NOT generic. Each name 6-14 words.\n\n"
        'Return ONLY a JSON object: {"templates": ["...", "..."]}\n\n'
        f"Parent template: {parent_name}\n"
    )
    raw = await _call(prompt, json_mode=True, max_tokens=512)
    if not raw:
        return []
    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        data = json.loads(raw)
        if isinstance(data, dict):
            for key in ("templates", "items", "names"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
        if isinstance(data, list):
            return [sanitize_text(str(x)).strip() for x in data
                    if isinstance(x, (str, int)) and str(x).strip()]
    except Exception:
        pass
    return []


async def check_document(filename, file_type, text):
    user = CHECKER_USER_TEMPLATE.format(
        filename=filename, file_type=file_type, text=text[:12000])
    raw = await _call(f"{CHECKER_SYSTEM_PROMPT}\n\n---\n\n{user}",
                      json_mode=True, max_tokens=4000)
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
    prompt = (
        "You are a senior Egyptian civil quality engineer. Answer the "
        "user's question using ONLY the knowledge base excerpts below. "
        "If the excerpts do not contain the answer, say so clearly and "
        "suggest which topic would help.\n\n"
        "ANSWER RULES:\n"
        "- 300-600 words.\n"
        "- Plain English, no LaTeX, no dollar signs.\n"
        "- Use markdown headings and bullet lists.\n"
        "- Cite the topic name in brackets when you quote an excerpt.\n"
        "- End with '## Related topics' list of 3-5 topics.\n\n"
        f"=== KNOWLEDGE BASE EXCERPTS ===\n{knowledge_context}\n\n"
        f"=== USER QUESTION ===\n{question}\n"
    )
    return await _call(prompt, json_mode=False, max_tokens=2048)


async def ocr_image(path):
    global last_error
    last_error = "OCR not supported on Groq provider"
    return ""
