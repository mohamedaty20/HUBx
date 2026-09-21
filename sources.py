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
    "wuzzuf.net",
    "bayt.com",
    "linkedin.com",
    "indeed.com",
    "tanqeeb.com",
    "forasna.com",
    "gulfTalent.com",
}

SOURCES = {
    # Tier A - official API / RSS feeds that work
    "reliefweb.int": TIER_A,      # UN OCHA - RSS of humanitarian jobs, Egypt + infra common
    "unjobs.org": TIER_A,         # UN jobs aggregator, RSS
    "weworkremotely.com": TIER_A, # RSS (remote dev, low yield but valid)

    # Tier C - manual paste only
    "wuzzuf.net": TIER_C,
    "bayt.com": TIER_C,
    "linkedin.com": TIER_C,
    "indeed.com": TIER_C,
    "tanqeeb.com": TIER_C,
    "forasna.com": TIER_C,
    "gulfTalent.com": TIER_C,

    # Tier D - blocked
    "facebook.com": TIER_D,
    "twitter.com": TIER_D,
}

LIVE_FETCH_URLS = {
    "reliefweb.int": "https://reliefweb.int/jobs/rss.xml",
    "unjobs.org": "https://unjobs.org/rss.xml",
    "weworkremotely.com": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
}

MANUAL_PASTE_DOMAINS = [d for d, t in SOURCES.items() if t == TIER_C]
BLOCKED_DOMAINS = {d for d, t in SOURCES.items() if t == TIER_D}


def get_tier(domain: str) -> str:
    return SOURCES.get(domain.lower().strip(), TIER_D)


def is_live_fetchable(domain: str) -> bool:
    return get_tier(domain) in (TIER_A, TIER_B)


def is_manual_paste(domain: str) -> bool:
    return get_tier(domain) == TIER_C
