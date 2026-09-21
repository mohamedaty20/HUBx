# sources.py
# Whitelist with per-domain tier. Developer-controlled.
# A = official API/RSS, B = HTML allowed after robots.txt,
# C = manual paste only (ToS forbids scraping), D = blocked.

MIN_DOMAIN_DELAY = 3.0

TIER_A = "A"
TIER_B = "B"
TIER_C = "C"
TIER_D = "D"

# Sites whose ToS explicitly forbid scraping. NEVER fetched live.
TOs_FORBIDDEN = {
    "wuzzuf.net",
    "bayt.com",
    "linkedin.com",
    "indeed.com",
    "tanqeeb.com",
    "forasna.com",
    "gulfTalent.com",
}

SOURCES = {
    # Tier A — official API / RSS
    "remoteok.com": TIER_A,
    "weworkremotely.com": TIER_A,
    "jobs.lever.co": TIER_A,
    "greenhouse.io": TIER_A,

    # Tier B — HTML allowed only after robots.txt check
    # "example-eng-board.com": TIER_B,

    # Tier C — manual paste only
    "wuzzuf.net": TIER_C,
    "bayt.com": TIER_C,
    "linkedin.com": TIER_C,
    "indeed.com": TIER_C,
    "tanqeeb.com": TIER_C,
    "forasna.com": TIER_C,
    "gulfTalent.com": TIER_C,

    # Tier D — blocked
    "facebook.com": TIER_D,
    "twitter.com": TIER_D,
}

LIVE_FETCH_URLS = {
    "remoteok.com": "https://remoteok.com/api",
    "weworkremotely.com": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "jobs.lever.co": None,
    "greenhouse.io": None,
}

MANUAL_PASTE_DOMAINS = [d for d, t in SOURCES.items() if t == TIER_C]
BLOCKED_DOMAINS = {d for d, t in SOURCES.items() if t == TIER_D}


def get_tier(domain: str) -> str:
    return SOURCES.get(domain.lower().strip(), TIER_D)


def is_live_fetchable(domain: str) -> bool:
    return get_tier(domain) in (TIER_A, TIER_B)


def is_manual_paste(domain: str) -> bool:
    return get_tier(domain) == TIER_C
