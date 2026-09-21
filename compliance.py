# compliance.py
"""
Compliance gate + errors for the fetching layer.

Exports:
    ComplianceError    base exception
    Blocked            raised when a URL must not be fetched (alias name)
    ComplianceGate     the gate class used by engine.py

Backwards compatibility: both `Blocked` and `ComplianceError` refer to the
same underlying exception class so older imports keep working.
"""

from __future__ import annotations

import asyncio
import time
import urllib.robotparser as urobot
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Optional

# Import the whitelist from sources.py. We import defensively so this
# file works even if sources.py is missing pieces.
try:
    from sources import (
        MIN_DOMAIN_DELAY,
        USER_AGENT,
        TIER_A,
        TIER_B,
        TIER_C,
        TIER_D,
        get_tier,
        get_min_delay,
        allowed_domains,
    )
except Exception:  # pragma: no cover - ultra-defensive fallback
    MIN_DOMAIN_DELAY = 3.0
    USER_AGENT = "EgyptCivilEngJobBot/1.0"
    TIER_A, TIER_B, TIER_C, TIER_D = [], [], [], []
    def get_tier(domain):  # type: ignore
        return "unknown"
    def get_min_delay(domain):  # type: ignore
        return MIN_DOMAIN_DELAY
    def allowed_domains():  # type: ignore
        return []


# ------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------
class ComplianceError(Exception):
    """Raised when a URL fails the compliance check."""


class Blocked(ComplianceError):
    """A URL is not allowed to be fetched live.

    This is a subclass of ComplianceError so `except ComplianceError`
    also catches Blocked.
    """


# ------------------------------------------------------------------
# Gate
# ------------------------------------------------------------------
@dataclass
class _SourceInfo:
    domain: str
    tier: str
    min_delay: float = MIN_DOMAIN_DELAY
    allowed_paths: list = field(default_factory=lambda: ["/"])
    note: str = ""


class ComplianceGate:
    """
    Checks a URL against the whitelist in sources.py:
      * unknown domain  -> Blocked
      * tier D          -> Blocked
      * tier C + fetch  -> Blocked (manual paste only)
      * robots.txt says no for live fetch -> Blocked
      * otherwise       -> allowed, with rate limiting per domain

    Usage:
        gate = ComplianceGate()
        await gate.check(url, kind="fetch")   # raises Blocked on failure
        await gate.check(url, kind="parse")   # user pasted content; no network
    """

    def __init__(self) -> None:
        self._robots: dict[str, Optional[urobot.RobotFileParser]] = {}
        self._last_hit: dict[str, float] = {}
        self._lock = asyncio.Lock()

    # ---------- public API ----------
    def allowed_domains(self) -> list:
        return allowed_domains()

    def tier_of(self, domain: str) -> str:
        return get_tier(domain)

    async def check(self, url: str, kind: str = "fetch") -> _SourceInfo:
        """
        kind='fetch' -> live request; full gate applies
        kind='parse' -> user pasted content; only tier D and unknown blocked
        """
        if not url:
            raise Blocked("empty url")

        parsed = urlparse(url if "://" in url else f"https://{url}")
        domain = (parsed.netloc or "").lower().removeprefix("www.")
        path = parsed.path or "/"

        if not domain:
            raise Blocked(f"could not parse domain from {url!r}")

        tier = get_tier(domain)
        if tier == "unknown":
            raise Blocked(f"{domain} is not on the whitelist")
        if tier == "D":
            raise Blocked(f"{domain} is on the blocklist (tier D)")
        if tier == "C" and kind == "fetch":
            raise Blocked(
                f"{domain} forbids scraping; use kind='parse' with pasted text"
            )

        # For parse mode we don't touch the network at all.
        if kind == "parse":
            return _SourceInfo(domain=domain, tier=tier,
                               min_delay=get_min_delay(domain))

        # Live fetch: check robots.txt (fail closed).
        robots_ok = await self._robots_ok(domain, path)
        if not robots_ok:
            raise Blocked(f"robots.txt disallows {path} on {domain}")

        # Rate limit per domain.
        delay = get_min_delay(domain)
        async with self._lock:
            last = self._last_hit.get(domain, 0.0)
            wait = delay - (time.monotonic() - last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_hit[domain] = time.monotonic()

        return _SourceInfo(domain=domain, tier=tier, min_delay=delay)

    # ---------- robots.txt ----------
    async def _robots_ok(self, domain: str, path: str) -> bool:
        if domain not in self._robots:
            rp = urobot.RobotFileParser()
            rp.set_url(f"https://{domain}/robots.txt")
            try:
                await asyncio.to_thread(rp.read)
            except Exception:
                # Fail closed: if robots.txt is unreachable, refuse.
                self._robots[domain] = None
                return False
            self._robots[domain] = rp

        rp = self._robots[domain]
        if rp is None:
            return False
        try:
            return bool(rp.can_fetch(USER_AGENT,
                                     f"https://{domain}{path}"))
        except Exception:
            return False
