# gemini.py
# v17: added expand_phase() for phase-based progression.

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
    PHASE_SYSTEM_PROMPT, PHASE_USER_TEMPLATE, PHASE_INSTRUCTIONS,
)

from db import (check_and_increment_gemini_usage,
                gemini_usage_stats)

logger = logging.getLogger(__name__)

MODEL = "openai/gpt-oss-20b"

GEMINI_DAY_LIMIT = int(os.getenv("GEMINI_DAY_LIMIT", "600"))
GEMINI_HOUR_LIMIT = int(os.getenv("GEMINI_HOUR_LIMIT", "40"))
_QUOTA_BLOCK_SECONDS = 240
ATTEMPT_TIMEOUT_SECONDS = 180
MIN_CALL_GAP = 240.0

_quota_block_until = 0.0
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

_client = None
if GROQ_API_KEY:
    _client = AsyncGroq(api_key=GROQ_API_KEY)

last_error = ""
_rate_lock = asyncio.Lock()
_last_call_time = 0.0


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
    (r"\\square\b", "□"), (r"\\Box\b", "□"),
    (r"\\checkmark\b", "✓"), (r"\\check\b", "✓"),
    (r"\\bullet\b", "•"), (r"\\cdots\b", "…"),
    (r"\\ldots\b", "…"), (r"\\dots\b", "…"),
]


def sanitize_text(s):
    if not s:
        return s
    s = str(s)
    s = re.sub(r"\\\(([^)]*)\\\)", r"\1", s)
    s = re.sub(r"\\\[([^\]]*)\\\]", r"\1", s)
    s = re.sub(r"\\text(?:bf|it|rm|sf|tt)?\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\math(?:bf|it|rm|sf|tt)\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\mathrm\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[A-Za-z]+\{([^{}]*)\}", r"\1", s)
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
            wait += random.uniform(0, 3.0)
            await asyncio.sleep(wait)
        _last_call_time = time.monotonic()


def _is_quota_error(err_str):
    s = (err_str or "").lower()
    return ("429" in s or "quota" in s or "rate limit" in s
            or "too many requests" in s or "exceeded" in s
            or ("tokens" in s and "limit" in s))


def _is_json_validation_error(err_str):
    s = (err_str or "").lower()
    return ("json_validate_failed" in s or "failed to generate json" in s
            or "max completion tokens reached" in s)


async def _call(prompt, json_mode=False, max_tokens=4000, max_retries=2):
    global last_error, _quota_block_until

    if not _client:
        last_error = "GROQ_API_KEY not set"
        return ""

    now_m = time.monotonic()
    if now_m < _quota_block_until:
        left = int(_quota_block_until - now_m)
        last_error = f"{MODEL}: cooling down, {left}s left"
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
            day_limit=GEMINI_DAY_LIMIT, hour_limit=GEMINI_HOUR_LIMIT)
        if not allowed:
            _quota_block_until = time.monotonic() + _QUOTA_BLOCK_SECONDS
            last_error = (f"{MODEL}: cap reached "
                          f"({GEMINI_HOUR_LIMIT}/hour), paused "
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
                last_error = (f"{MODEL}: Groq 429, cooling "
                              f"{_QUOTA_BLOCK_SECONDS}s")
                logger.warning(last_error)
                return ""
            if _is_json_validation_error(err_str):
                last_error = f"{MODEL}: JSON too large for budget"
                logger.warning(last_error)
                return ""
            last_error = f"{MODEL}: {err_str}"
            logger.warning("LLM call failed (attempt %d): %s", attempt + 1, e)
            await asyncio.sleep(4 * (attempt + 1))
    return ""


async def generate_knowledge(topic, category):
    user = KNOWLEDGE_USER_TEMPLATE.format(topic=topic, category=category)
    return await _call(f"{KNOWLEDGE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=4000)


async def refine_knowledge(topic, existing):
    user = REFINE_USER_TEMPLATE.format(topic=topic, content=existing[:6000])
    return await _call(f"{REFINE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=4000)


async def generate_template(name, category):
    user = TEMPLATE_USER_TEMPLATE.format(name=name, category=category)
    return await _call(f"{TEMPLATE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=4000)


async def refine_template(name, existing):
    return await _call(
        "Improve the following construction template. Keep it FULLY "
        "BILINGUAL. Sample Filled Example MUST be a markdown table. "
        "Never use <br>. No LaTeX, no \\square, no \\(...\\).\n\n"
        "---\n\n"
        f"Template: {name}\n\n{existing[:6000]}",
        json_mode=False, max_tokens=4000)


async def expand_phase(title, category, current_content,
                       current_phase, target_phase):
    """Advance a document to the next phase by appending a new section."""
    instructions = PHASE_INSTRUCTIONS.get(target_phase, "")
    if not instructions:
        return ""
    user = PHASE_USER_TEMPLATE.format(
        title=title,
        category=category,
        current_phase=current_phase,
        target_phase=target_phase,
        phase_instructions=instructions,
        existing=current_content[:8000],
    )
    return await _call(f"{PHASE_SYSTEM_PROMPT}\n\n---\n\n{user}",
                       json_mode=False, max_tokens=4500)


async def suggest_subtopics(parent_topic, category, n=2):
    prompt = (
        f"Return a JSON object with one key 'subtopics' whose value is "
        f"an array of exactly {n} short bilingual strings. "
        f"Category: {category}. Parent: {parent_topic}. "
        "Each string: 'English Title / العربية'. English part 4-8 words. "
        "Keep total output under 200 tokens."
    )
    raw = await _call(prompt, json_mode=True, max_tokens=1500)
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


async def suggest_subtemplates(parent_name, category, n=2):
    prompt = (
        f"Return a JSON object with one key 'templates' whose value is "
        f"an array of exactly {n} short bilingual strings. "
        f"Category: {category}. Parent: {parent_name}. "
        "Each string: 'English Name / الاسم بالعربية'. English part "
        "4-8 words. Keep total output under 200 tokens."
    )
    raw = await _call(prompt, json_mode=True, max_tokens=1500)
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
                      json_mode=True, max_tokens=3000)
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
        "You are a senior Egyptian civil quality engineer. Answer using "
        "ONLY the excerpts below. No LaTeX, no <br>.\n\n"
        "RULES:\n- 300-600 words.\n- Markdown headings and bullets.\n"
        "- Cite topic names in brackets.\n"
        "- End with '## Related topics'.\n\n"
        f"=== EXCERPTS ===\n{knowledge_context}\n\n"
        f"=== QUESTION ===\n{question}\n"
    )
    return await _call(prompt, json_mode=False, max_tokens=1500)


async def ocr_image(path):
    global last_error
    last_error = "OCR not supported on Groq provider"
    return ""
