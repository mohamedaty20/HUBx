# HUBx — Self-Refining Civil Engineering Job Intelligence (Egypt)

Searches for civil-engineering jobs in Egypt posted in the last 7 days,
extracts full descriptions and recruiter details **only from public postings**,
stores everything in Turso, and renders NiceGUI dashboards.

## Stack
- Python 3.11+
- NiceGUI (UI + dashboards)
- Turso (libsql) database
- Gemini API (`gemini-3.5-flash-lite`) — the only AI used
- httpx, BeautifulSoup4, feedparser
- Render (free tier supported)

## Setup

### 1. Turso Database
```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create hubx
turso db show hubx --url
turso db tokens create hubx
