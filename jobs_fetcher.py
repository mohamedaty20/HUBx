# jobs_fetcher.py — HUBx Job Board Scraper
# Fetch a page (Playwright for JS-heavy, httpx+BS4 for static) and return
# (ok, final_url, text, links) where links are candidate job-posting URLs.

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36"
)
TIMEOUT = 30.0
MAX_BYTES = 900_000

# Words that usually indicate a DIRECT job posting link, not a nav link.
JOB_URL_HINTS = (
    "/job/", "/jobs/", "/career", "/careers", "/vacanc", "/position",
    "/opening", "/opening-", "/apply", "/posting", "/role", "/hiring",
    "jobid=", "job_id=", "requisition",
)

# Words to exclude outright (nav, social, legal, listing pages).
NAV_BLOCKLIST = (
    "facebook.com", "twitter.com", "x.com", "linkedin.com/company",
    "instagram.com", "youtube.com", "tiktok.com",
    "privacy", "terms", "cookie", "contact", "about", "login",
    "signin", "sign-in", "signup", "sign-up", "register",
    "mailto:", "tel:", "javascript:", "#",
)


def fetch_page(url, kind="html"):
    """Return (ok, final_url, text, links). links is a list of absolute URLs."""
    if not url:
        return False, url, "empty url", []
    if kind == "js":
        return _fetch_playwright(url)
    return _fetch_static(url)


# ── Static path: httpx + BeautifulSoup ───────────────────────────────────
def _fetch_static(url):
    try:
        headers = {"User-Agent": USER_AGENT,
                   "Accept-Language": "ar,en;q=0.8"}
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                          headers=headers) as client:
            r = client.get(url)
            if r.status_code >= 400:
                return False, url, f"HTTP {r.status_code}", []
            ctype = (r.headers.get("content-type") or "").lower()
            if "pdf" in ctype:
                return False, url, "pdf not supported", []
            html = r.text[:MAX_BYTES]
            final_url = str(r.url)
            text = _html_to_text(html)
            links = _extract_links(html, final_url)
            return True, final_url, text, links
    except Exception as e:
        return False, url, f"{type(e).__name__}: {e}", []


# ── JS path: Playwright (Chromium headless) ──────────────────────────────
def _fetch_playwright(url):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        return False, url, f"playwright not installed: {e}", []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                ctx = browser.new_context(user_agent=USER_AGENT,
                                          locale="en-US")
                page = ctx.new_page()
                page.goto(url, wait_until="networkidle", timeout=45_000)
                # Give late XHR content a moment to settle.
                page.wait_for_timeout(1200)
                final_url = page.url
                html = page.content()
            finally:
                browser.close()
        if not html:
            return False, final_url, "empty html", []
        text = _html_to_text(html)
        links = _extract_links(html, final_url)
        return True, final_url, text, links
    except Exception as e:
        return False, url, f"{type(e).__name__}: {e}", []


# ── HTML → text (same shape as prices_fetcher) ───────────────────────────
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(
    r"<(script|style|noscript|svg|iframe)[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


def _html_to_text(html):
    if not html:
        return ""
    s = _SCRIPT_RE.sub(" ", html)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.DOTALL)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"</(p|div|li|tr|h[1-6])>", "\n", s, flags=re.IGNORECASE)
    s = _TAG_RE.sub(" ", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&")
         .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    s = _WS_RE.sub(" ", s)
    s = _NL_RE.sub("\n\n", s)
    return s.strip()[:60000]


# ── Link extraction ──────────────────────────────────────────────────────
def _extract_links(html, base_url):
    """Return a de-duped list of absolute URLs on the same host that look
    like direct job-posting links."""
    if not html:
        return []
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []
    base_host = urlparse(base_url).netloc.lower()
    seen = set()
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        low = href.lower()
        if any(b in low for b in NAV_BLOCKLIST):
            continue
        abs_url = urljoin(base_url, href)
        u = urlparse(abs_url)
        if u.scheme not in ("http", "https"):
            continue
        # Same host only — job postings on a company site are usually same-host.
        if u.netloc.lower() != base_host:
            continue
        # Strip fragments.
        clean = abs_url.split("#", 1)[0]
        if clean in seen:
            continue
        # Filter: must look like a job URL. If the site uses a totally
        # different pattern, admins can still get links because we keep
        # any URL whose last path segment has >=2 hyphens and no file ext.
        last = u.path.rsplit("/", 1)[-1].lower()
        looks_job = any(h in low for h in JOB_URL_HINTS)
        looks_slug = ("-" in last and "." not in last and len(last) > 12)
        if not (looks_job or looks_slug):
            continue
        # Drop obvious listing roots.
        if u.path in ("", "/", "/jobs", "/careers", "/job", "/career"):
            continue
        seen.add(clean)
        out.append(clean)
    return out[:60]
