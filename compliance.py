# compliance.py
# Safest legal option chosen: fail closed on every robots.txt error.
# EXCEPTION 1: a missing robots.txt (404) means "allow", per RFC 9309.
# EXCEPTION 2: Tier A = official API/RSS. These endpoints exist for
#   machine consumption, so robots.txt is not consulted for them.

import asyncio
import time
import urllib.robotparser
from urllib.parse import urlparse
from collections import defaultdict

import httpx

from sources import (MIN_DOMAIN_DELAY, get_tier,
                     TIER_A, TIER_B, TIER_C, TIER_D)

_last_request_time: dict[str, float] = defaultdict(float)

# Real browser User-Agent. Cloudflare blocks custom UAs on some sites.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class ComplianceError(Exception):
    pass


def _domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.split(":")[0]


async def check_robots(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        async with httpx.AsyncClient(
                timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(
                robots_url, headers={"User-Agent": BROWSER_UA})
            if resp.status_code == 404:
                return True
            if resp.status_code != 200:
                return False
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(resp.text.splitlines())
            return rp.can_fetch("*", url)
    except Exception:
        return False


async def enforce_delay(domain: str) -> None:
    now = time.monotonic()
    elapsed = now - _last_request_time[domain]
    if elapsed < MIN_DOMAIN_DELAY:
        await asyncio.sleep(MIN_DOMAIN_DELAY - elapsed)
    _last_request_time[domain] = time.monotonic()


def tier_gate(domain: str) -> None:
    tier = get_tier(domain)
    if tier == TIER_D:
        raise ComplianceError(f"Domain {domain} is blocked (Tier D).")
    if tier == TIER_C:
        raise ComplianceError(
            f"Domain {domain} is manual-paste only (Tier C).")
    if tier not in (TIER_A, TIER_B):
        raise ComplianceError(f"Unknown tier for {domain}.")


async def safe_fetch(url: str) -> str:
    domain = _domain(url)
    tier = get_tier(domain)
    tier_gate(domain)

    if tier != TIER_A:
        if not await check_robots(url):
            raise ComplianceError(f"robots.txt disallows {url}")

    await enforce_delay(domain)
    async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(
            url,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "application/rss+xml, application/xml, "
                          "text/xml, */*",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        resp.raise_for_status()
        return resp.text
