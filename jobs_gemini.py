# jobs_gemini.py — HUBx Job Board Scraper
# Groq wrapper for the job summarizer. Anti-hallucination prompt.

from __future__ import annotations

import os
import re
import json
import asyncio
import logging
import time
import random

from groq import AsyncGroq

logger = logging.getLogger(__name__)

MODEL = "openai/gpt-oss-20b"
REASONING_EFFORT = os.getenv("REASONING_EFFORT", "low")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

_client = None
if GROQ_API_KEY:
    _client = AsyncGroq(api_key=GROQ_API_KEY)

last_error = ""
_rate_lock = asyncio.Lock()
_last_call_time = 0.0
MIN_CALL_GAP = 3.0


async def _throttle():
    global _last_call_time
    async with _rate_lock:
        now = time.monotonic()
        wait = MIN_CALL_GAP - (now - _last_call_time)
        if wait > 0:
            wait += random.uniform(0, 1.5)
            await asyncio.sleep(wait)
        _last_call_time = time.monotonic()


def _extract_content(resp):
    try:
        msg = resp.choices[0].message
    except Exception:
        return ""
    c = getattr(msg, "content", None)
    if isinstance(c, str) and c.strip():
        return c.strip()
    return ""


async def _groq(prompt, max_tokens=1500, json_mode=True):
    global last_error
    if not _client:
        last_error = "GROQ_API_KEY not set"
        return ""
    await _throttle()
    kwargs = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "reasoning_effort": REASONING_EFFORT,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = await asyncio.wait_for(
            _client.chat.completions.create(**kwargs), timeout=120)
        text = _extract_content(resp)
        if not text:
            last_error = "empty content"
            return ""
        last_error = ""
        return text
    except Exception as e:
        last_error = f"{type(e).__name__}: {e}"
        logger.warning("Groq call failed: %s", e)
        return ""


def _strip_fences(s):
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        s = s.rsplit("```", 1)[0]
    return s.strip()


JOB_SYSTEM = """You are a data-extraction assistant that summarizes job postings
for Egyptian civil engineers. You extract only what the page actually says.
You never invent, guess, or embellish.

Return ONLY valid JSON, no commentary, no markdown fences.

Schema:
{
  "title": "short, clean job title",
  "company": "as written on the page",
  "location": "City, Country  (or Remote / Hybrid)",
  "employment_type": "Full-time / Part-time / Contract / Internship / unknown",
  "experience_level": "Entry / Mid / Senior / Lead / unknown",
  "posted_date": "YYYY-MM-DD or empty",
  "posted_date_confidence": 0.0,
  "summary_points": [
    "Short bullet (max ~15 words)",
    "Short bullet",
    "Short bullet",
    "Short bullet",
    "Short bullet"
  ],
  "requirements_points": [
    "Short bullet",
    "Short bullet",
    "Short bullet"
  ],
  "key_skills": ["skill1","skill2","skill3"]
}

Hard rules — do not break any of these:
- Every bullet must be a summary of the source text, not a copy-paste.
  Paraphrase. If a source sentence is longer than ~15 words, shorten it.
  Never reproduce an original paragraph verbatim.
- Never include personal names, emails, phone numbers, WhatsApp links,
  or anything that identifies an individual recruiter.
- Never invent a field. If the page does not state the posted date,
  leave posted_date as "" and set posted_date_confidence to 0.0.
- The apply_url MUST be the direct URL the crawler visited to read the
  posting. If the page redirected, use the final URL. Never the listing page.
- English only for title, company, and bullets.
- summary_points: 3 to 5 bullets. requirements_points: 2 to 5 bullets.
- key_skills: 3 to 8 short skill tags (single words or two-word tags).
- If the page is not a job posting at all, return:
  {"error":"not_a_job_posting"}
"""


async def summarize_job(page_text, page_url, company_hint=""):
    """Return a dict matching JOB_SYSTEM, or {"error": "..."} on failure."""
    if not page_text or len(page_text) < 200:
        return {"error": "page_too_short"}

    snippet = page_text[:20000]
    prompt = (
        f"{JOB_SYSTEM}\n\n"
        f"Company hint: {company_hint or '(unknown)'}\n"
        f"Source URL (this is the apply_url to use): {page_url}\n\n"
        f"Page text:\n\"\"\"\n{snippet}\n\"\"\"\n\n"
        "Return the JSON now."
    )
    raw = await _groq(prompt, max_tokens=1600, json_mode=True)
    if not raw:
        return {"error": "groq_empty"}

    try:
        data = json.loads(_strip_fences(raw))
    except Exception as e:
        logger.warning("summarize_job: JSON parse failed: %s", e)
        return {"error": "json_parse_failed"}

    if not isinstance(data, dict):
        return {"error": "json_not_object"}
    if data.get("error"):
        return {"error": str(data["error"])[:80]}

    # Sanitize fields.
    def _s(v, n):
        return str(v or "").strip()[:n]

    def _clean_bullets(lst, max_n, max_words=20):
        out = []
        if not isinstance(lst, list):
            return out
        for b in lst:
            t = _s(b, 220)
            if not t:
                continue
            if len(t.split()) > max_words:
                t = " ".join(t.split()[:max_words])
            out.append(t)
            if len(out) >= max_n:
                break
        return out

    skills = []
    for s in (data.get("key_skills") or []):
        t = _s(s, 40)
        if t and len(t) >= 2:
            skills.append(t)
        if len(skills) >= 8:
            break

    try:
        conf = float(data.get("posted_date_confidence", 0.0) or 0.0)
    except Exception:
        conf = 0.0
    conf = max(0.0, min(1.0, conf))

    posted = _s(data.get("posted_date"), 32)
    # Strict ISO date or empty.
    if posted and not re.match(r"^\d{4}-\d{2}-\d{2}$", posted):
        posted = ""
        conf = 0.0

    title = _s(data.get("title"), 200)
    if not title or len(title) < 2:
        return {"error": "missing_title"}

    return {
        "title": title,
        "company": _s(data.get("company"), 200),
        "location": _s(data.get("location"), 200),
        "employment_type": _s(data.get("employment_type"), 40) or "unknown",
        "experience_level": _s(data.get("experience_level"), 40) or "unknown",
        "posted_date": posted,
        "posted_date_confidence": conf,
        "apply_url": page_url,
        "summary_points": _clean_bullets(data.get("summary_points"), 5),
        "requirements_points": _clean_bullets(data.get("requirements_points"), 5),
        "key_skills": skills,
    }
