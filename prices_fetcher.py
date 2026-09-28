# prices_fetcher.py
# Minimal HTML fetcher for the prices engine.
# Uses httpx only. No Cloudflare Browser Run.

import logging
import re

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Mobile Safari/537.36"
)
TIMEOUT = 25.0
MAX_BYTES = 900_000


def fetch_page(url):
    """Fetch a URL and return cleaned text. Returns (ok, text_or_error)."""
    if not url:
        return False, "empty url"
    try:
        headers = {"User-Agent": USER_AGENT,
                   "Accept-Language": "ar,en;q=0.8"}
        with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                          headers=headers) as client:
            r = client.get(url)
            if r.status_code >= 400:
                return False, f"HTTP {r.status_code}"
            ctype = (r.headers.get("content-type") or "").lower()
            if "pdf" in ctype:
                return False, "pdf not supported in this fetcher"
            html = r.text[:MAX_BYTES]
            return True, _html_to_text(html)
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


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
