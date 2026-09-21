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
    "unjobs.org",  # explicitly forbids automated access
}

SOURCES = {
    # Tier A - official RSS feeds that actually produce Egypt jobs
    "reliefweb.int": TIER_A,
    "weworkremotely.com": TIER_A,

    # Tier C - manual paste only
    "wuzzuf.net": TIER_C,
    "bayt.com": TIER_C,
    "linkedin.com": TIER_C,
    "indeed.com": TIER_C,
    "tanqeeb.com": TIER_C,
    "forasna.com": TIER_C,
    "gulfTalent.com": TIER_C,
    "unjobs.org": TIER_C,  # ToS forbids scraping - manual only

    # Tier D - blocked
    "facebook.com": TIER_D,
    "twitter.com": TIER_D,
}

# ReliefWeb publishes filtered RSS feeds by country/category.
# The Egypt job feed uses their advanced-search parameter.
LIVE_FETCH_URLS = {
    # ReliefWeb jobs filtered to Egypt (country id PC182 is Egypt on ReliefWeb)
    "reliefweb.int": "https://reliefweb.int/jobs/rss.xml?advanced-search=%28PC182%29",
    # WeWorkRemotely as a fallback (low yield for civil eng, but legal)
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
