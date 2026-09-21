# compliance.py
# Safest legal option chosen: fail closed on every robots.txt error.
# EXCEPTION: a missing robots.txt (404) means "allow", per RFC 9309.
# No proxies, no CAPTCHA solving, no fingerprint spoofing.

import asyncio
import time
import urllib.robotparser
from urllib.parse import urlparse
from collections import defaultdict

import httpx

from sources import MIN_DOMAIN_DELAY, get_tier, TIER_A, TIER_B, TIER_C, TIER_D

_last_request_time: dict[str, float] = defaultdict(float)


class ComplianceError(Exception):
    pass


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "", 1)


async def check_robots(url: str) -> bool:
    """
    RFC 9309: if robots.txt is absent (404), access is allowed.
    Any other error (timeout, 5xx) fails closed.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(robots_url)
            if resp.status_code == 404:
                return True  # no robots.txt = allow all
            if resp.status_code != 200:
                return False  # fail closed on anything else
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
            f"Domain {domain} is manual-paste only (Tier C)."
        )
    if tier not in (TIER_A, TIER_B):
        raise ComplianceError(f"Unknown tier for {domain}.")


async def safe_fetch(url: str) -> str:
    domain = _domain(url)
    tier_gate(domain)
    if not await check_robots(url):
        raise ComplianceError(f"robots.txt disallows {url}")
    await enforce_delay(domain)
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(
            url, headers={"User-Agent": "HUBx/1.0 (+civil-eng-jobs)"}
        )
        resp.raise_for_status()
        return resp.text
