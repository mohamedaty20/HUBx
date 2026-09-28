# prices_gemini.py
# Groq-based extraction of material prices, categories, and regions.

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


async def _groq(prompt, max_tokens=2000, json_mode=True):
    global last_error
    if not _client:
        last_error = "GROQ_API_KEY not set"
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


PRICE_SYSTEM = """You are a data-extraction assistant for Egyptian
construction-material prices.

Return ONLY valid JSON, no commentary, no markdown fences.

Schema:
{
  "prices": [
    {
      "material": "English name of the material",
      "spec": "short spec / grade / size (or empty)",
      "price": 12345.6,
      "currency": "EGP",
      "unit": "ton / m3 / bag / piece / m2",
      "region": "Cairo / Alexandria / all Egypt / unknown",
      "confidence": 0.0
    }
  ],
  "new_categories": [
    {"name": "English name", "parent": "parent category name or empty"}
  ],
  "new_regions": ["Cairo", "Alexandria"]
}

Rules:
- Only include prices that are clearly stated in the text.
- Do NOT invent prices. If unsure, drop the item.
- Normalize price to a number (no commas, no currency symbols).
- "confidence" 0.0-1.0 based on how clearly the source stated it.
- "new_categories" should list materials categories you saw that are not
  in the existing list.
- English only for category/material names.
"""


async def extract_prices(page_text, source_name, existing_categories):
    if not page_text:
        return {"prices": [], "new_categories": [], "new_regions": []}
    snippet = page_text[:25000]
    cats = ", ".join(existing_categories[:60]) if existing_categories else "(none yet)"
    prompt = (
        f"{PRICE_SYSTEM}\n\n"
        f"Existing categories: {cats}\n\n"
        f"Source: {source_name}\n\n"
        f"Page text:\n\"\"\"\n{snippet}\n\"\"\"\n\n"
        "Return the JSON now."
    )
    raw = await _groq(prompt, max_tokens=2500, json_mode=True)
    if not raw:
        return {"prices": [], "new_categories": [], "new_regions": []}
    try:
        data = json.loads(_strip_fences(raw))
    except Exception as e:
        logger.warning("extract_prices: JSON parse failed: %s", e)
        return {"prices": [], "new_categories": [], "new_regions": []}
    if not isinstance(data, dict):
        return {"prices": [], "new_categories": [], "new_regions": []}
    prices = data.get("prices") or []
    clean_prices = []
    for p in prices:
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
    for c in (data.get("new_categories") or []):
        if isinstance(c, dict):
            nm = str(c.get("name", "")).strip()[:120]
            if nm and len(nm) >= 2:
                new_cats.append({
                    "name": nm,
                    "parent": str(c.get("parent", "")).strip()[:120] or None,
                })
        elif isinstance(c, str):
            nm = c.strip()[:120]
            if nm and len(nm) >= 2:
                new_cats.append({"name": nm, "parent": None})
    new_regions = []
    for r in (data.get("new_regions") or []):
        if isinstance(r, str):
            nm = r.strip()[:120]
            if nm:
                new_regions.append(nm)
    return {"prices": clean_prices,
            "new_categories": new_cats,
            "new_regions": new_regions}
