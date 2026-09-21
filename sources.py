# sources.py
# Whitelist with per-domain tier. Developer-controlled.
# A = official API/RSS, B = HTML allowed after robots.txt,
# C = manual paste only (ToS forbids scraping), D = blocked.

MIN_DOMAIN_DELAY = 3.0

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
TIER_D = "D"

TOs_FORBIDDEN = {
    "wuzzuf.net", "bayt.com", "linkedin.com", "indeed.com",
    "tanqeeb.com", "forasna.com", "gulfTalent.com",
    "unjobs.org", "reliefweb.int",
}

SOURCES = {
    "unjoblink.org": TIER_A,
    "weworkremotely.com": TIER_A,

    "wuzzuf.net": TIER_C,
    "bayt.com": TIER_C,
    "linkedin.com": TIER_C,
    "indeed.com": TIER_C,
    "tanqeeb.com": TIER_C,
    "forasna.com": TIER_C,
    "gulfTalent.com": TIER_C,
    "unjobs.org": TIER_C,
    "naqrajobs.com": TIER_C,

    "facebook.com": TIER_D,
    "twitter.com": TIER_D,
}

LIVE_FETCH_URLS = {
    "unjoblink.org": "https://unjoblink.org/?feed=job_feed",
    "weworkremotely.com": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
}

FALLBACK_URLS = {
    "unjoblink.org": [
        "https://unjoblink.org/?feed=job_feed&iwj_location=cairo",
        "https://unjoblink.org/?feed=job_feed&iwj_location=egypt",
    ],
}

MANUAL_PASTE_DOMAINS = [d for d, t in SOURCES.items() if t == TIER_C]
BLOCKED_DOMAINS = {d for d, t in SOURCES.items() if t == TIER_D}


def get_tier(domain: str) -> str:
    return SOURCES.get(domain.lower().strip(), TIER_D)


def is_live_fetchable(domain: str) -> bool:
    return get_tier(domain) in (TIER_A, TIER_B)


def is_manual_paste(domain: str) -> bool:
    return get_tier(domain) == TIER_C
