# prices_gemini.py
# Groq-based extraction of material prices, categories, and regions.
# v2: much smaller prompts, shared daily quota, 429-aware.

import os
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

# Small model + small prompt = small token budget.
# Groq's free daily token limit is 200k. Keep each call under ~4000 tokens
# so we can still do ~50 calls per day without hitting the ceiling.
MAX_INPUT_CHARS = 6000
MAX_OUTPUT_TOKENS = 1500

_client = None
if GROQ_API_KEY:
    _client = AsyncGroq(api_key=GROQ_API_KEY)

last_error = ""
_rate_lock = asyncio.Lock()
_last_call_time = 0.0
MIN_CALL_GAP = 8.0  # seconds between calls — keeps us well under 30 req/min

# Shared daily-cap gate — imported from the main db module.
def _usage_gate():
    try:
        from db import check_and_increment_gemini_usage
        return check_and_increment_gemini_usage(day_limit=600, hour_limit=40)
    except Exception:
        return True


async def _throttle():
    global _last_call_time
    async with _rate_lock:
        now = time.monotonic()
        wait = MIN_CALL_GAP - (now - _last_call_time)
        if wait > 0:
            wait += random.uniform(0, 2.0)
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


async def _groq(prompt, max_tokens=MAX_OUTPUT_TOKENS, json_mode=True):
    global last_error
    if not _client:
        last_error = "GROQ_API_KEY not set"
        return ""
    if not _usage_gate():
        last_error = "shared daily cap reached"
        return ""

    await _throttle()
    kwargs = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "reasoning_effort": REASONING_EFFORT,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = await asyncio.wait_for(
            _client.chat.completions.create(**kwargs), timeout=90)
        text = _extract_content(resp)
        if not text:
            last_error = "empty content"
            return ""
        last_error = ""
        return text
    except Exception as e:
        msg = str(e)
        # Detect the 429/token-limit error precisely.
        if "429" in msg or "rate_limit" in msg.lower() or "tokens per day" in msg.lower():
            last_error = "429 quota — cooling down"
            logger.warning("Groq 429: %s", msg[:200])
            return ""
        last_error = f"{type(e).__name__}: {msg[:120]}"
        logger.warning("Groq call failed: %s", msg[:200])
        return ""


def _strip_fences(s):
    if s.startswith("```"):
        s = s.split("\n", 1)[-1]
        s = s.rsplit("```", 1)[0]
    return s.strip()


PRICE_SYSTEM = (
    "Extract construction material prices from the text. "
    "Return ONLY JSON: "
    '{"prices":[{"material":"","spec":"","price":0,'
    '"currency":"EGP","unit":"","region":"","confidence":0.5}],'
    '"new_categories":[{"name":"","parent":""}],"new_regions":[""]}. '
    "Only include prices clearly stated. Never invent prices. "
    "Drop anything uncertain. English material names."
)


async def extract_prices(page_text, source_name, existing_categories):
    if not page_text:
        return {"prices": [], "new_categories": [], "new_regions": []}

    # Hard-truncate to keep the token count low.
    snippet = page_text[:MAX_INPUT_CHARS]

    # Skip obviously useless pages before spending a token.
    if len(snippet) < 400:
        return {"prices": [], "new_categories": [], "new_regions": []}

    cats = ", ".join(existing_categories[:30]) if existing_categories else "(none)"
    prompt = (
        f"{PRICE_SYSTEM}\n\n"
        f"Existing categories: {cats}\n"
        f"Source name: {source_name}\n\n"
        f"Page text:\n{snippet}\n\n"
        "Return the JSON now."
    )
    raw = await _groq(prompt)
    if not raw:
        return {"prices": [], "new_categories": [], "new_regions": []}
    try:
        data = json.loads(_strip_fences(raw))
    except Exception as e:
        logger.warning("extract_prices JSON parse failed: %s", e)
        return {"prices": [], "new_categories": [], "new_regions": []}
    if not isinstance(data, dict):
        return {"prices": [], "new_categories": [], "new_regions": []}

    clean_prices = []
    for p in (data.get("prices") or [])[:40]:
        if not isinstance(p, dict):
            continue
        try:
            price = float(str(p.get("price", "")).replace(",", "").strip())
        except Exception:
            continue
        if price <= 0 or price > 1_000_000_000:
            continue
        mat = str(p.get("material", "")).strip()[:200]
        if not mat or len(mat) < 3:
            continue
        clean_prices.append({
            "material": mat,
            "spec": str(p.get("spec", "")).strip()[:120] or None,
            "price": price,
            "currency": str(p.get("currency", "EGP")).strip()[:8] or "EGP",
            "unit": str(p.get("unit", "")).strip()[:40] or None,
            "region": str(p.get("region", "")).strip()[:120] or None,
            "confidence": max(0.0, min(1.0, float(p.get("confidence", 0.5) or 0.5))),
        })

    new_cats = []
    for c in (data.get("new_categories") or [])[:20]:
        if isinstance(c, dict):
            nm = str(c.get("name", "")).strip()[:120]
            if nm and len(nm) >= 2:
                new_cats.append({
                    "name": nm,
                    "parent": str(c.get("parent", "")).strip()[:120] or None,
                })

    new_regions = []
    for r in (data.get("new_regions") or [])[:20]:
        if isinstance(r, str):
            nm = r.strip()[:120]
            if nm:
                new_regions.append(nm)

    return {"prices": clean_prices,
            "new_categories": new_cats,
            "new_regions": new_regions}
