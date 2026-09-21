# engine.py
"""
70-second autonomous loop with real pause/start.
- Every cycle: run whichever pipelines are enabled by STATE.focus
- Every 5th cycle: 1 Gemini call to refine the strategy
- Pause cancels the loop task AND guards every Gemini call before + after
- All jobs filtered to Egypt + civil engineering + last 7 days
"""
from __future__ import annotations
import asyncio, json, os, re, traceback
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
import feedparser

from state import STATE
from compliance import ComplianceGate, Blocked

# ---------- config ----------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL   = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
GEMINI_URL     = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
)
CYCLE_SECONDS   = 70.0
REFINE_EVERY    = 5
HTTP_TIMEOUT    = 20.0
USER_AGENT      = "EgyptCivilEngJobBot/1.0 (+contact: you@example.com)"

# ---------- Egypt + civil-engineering filter ----------
EGYPT_CITIES = {
    "cairo", "giza", "alexandria", "new cairo", "6th of october", "october 6",
    "mansoura", "tanta", "aswan", "luxor", "port said", "suez", "ismailia",
    "hurghada", "sharm", "sharm el sheikh", "sohag", "assiut", "damietta",
    "fayoum", "beni suef", "minya", "qena", "damanhur", "zagazig", "egypt",
}
CIVIL_KEYWORDS = {
    "civil", "structural", "site engineer", "geotechnical", "transportation",
    "highway", "water resources", "sanitary", "irrigation", "construction management",
    "quantity surveying", "qs", "bim", "concrete", "steel design", "infrastructure",
    "bridges", "tunnels", "marine", "surveying", "planning engineer",
    "هندسة مدنية", "مدني", "إنشائي", "طرق", "كباري", "مياه", "صرف", "مساحة",
}

def _norm(s: str) -> str:
    return (s or "").lower()

def is_egypt_civil(text: str) -> bool:
    t = _norm(text)
    return any(c in t for c in EGYPT_CITIES) and any(k in t for k in CIVIL_KEYWORDS)

def within_7_days(d: str | None) -> bool:
    if not d:
        return False
    try:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - dt <= timedelta(days=7)
    except Exception:
        return False

# ---------- DB layer (Turso via libsql-client) ----------
class DB:
    """
    Thin wrapper. Replace with your real libsql/Turso client if you already have one.
    Falls back to a simple in-memory store if Turso env vars are missing, so the
    engine never crashes on first run.
    """
    def __init__(self):
        self.url   = os.environ.get("TURSO_URL", "")
        self.token = os.environ.get("TURSO_TOKEN", "")
        self._mem_jobs: list[dict] = []
        self._mem_runs: list[dict] = []
        self._mem_strat: list[dict] = []
        self._mem_fail: list[dict] = []
        self._conn = None
        self._ready = False

    async def init(self):
        if self._ready:
            return
        if self.url and self.token:
            try:
                import libsql_client
                self._conn = libsql_client.create_client_sync(
                    url=self.url, auth_token=self.token
                )
                self._create_schema()
            except Exception as e:
                print(f"[DB] Turso unavailable, using memory: {e}")
                self._conn = None
        self._ready = True

    def _create_schema(self):
        c = self._conn
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, company TEXT, location TEXT, posted_date TEXT,
            url TEXT UNIQUE, description_full TEXT,
            recruiter_name TEXT, recruiter_title TEXT, recruiter_contact TEXT,
            source_domain TEXT, source_tier TEXT,
            relevance_score REAL, quality_score REAL,
            first_seen TEXT, expires_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS strategies(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT, queries_json TEXT, sources_json TEXT,
            reasoning TEXT, confidence REAL, active INTEGER DEFAULT 1)""")
        c.execute("""CREATE TABLE IF NOT EXISTS runs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER, started_at TEXT, finished_at TEXT,
            fetched INTEGER, kept INTEGER, errors INTEGER)""")
        c.execute("""CREATE TABLE IF NOT EXISTS failures(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER, query TEXT, domain TEXT,
            error_type TEXT, error_msg TEXT, created_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS knowledge(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT, answer TEXT, source_model TEXT,
            quality_score REAL, confidence REAL, topic_cluster TEXT,
            created_at TEXT, parent_id INTEGER, status TEXT DEFAULT 'active')""")
        c.execute("""CREATE TABLE IF NOT EXISTS templates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER, lang TEXT, html TEXT, created_at TEXT)""")

    async def insert_job(self, job: dict) -> bool:
        await self.init()
        # dedupe by url
        if self._conn:
            try:
                self._conn.execute(
                    """INSERT OR IGNORE INTO jobs(
                        title, company, location, posted_date, url, description_full,
                        recruiter_name, recruiter_title, recruiter_contact,
                        source_domain, source_tier, relevance_score, quality_score,
                        first_seen, expires_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (job.get("title"), job.get("company"), job.get("location"),
                     job.get("posted_date"), job.get("url"),
                     job.get("description_full"), job.get("recruiter_name"),
                     job.get("recruiter_title"), job.get("recruiter_contact"),
                     job.get("source_domain"), job.get("source_tier"),
                     job.get("relevance_score", 0.0), job.get("quality_score", 0.0),
                     datetime.utcnow().isoformat(),
                     (datetime.utcnow() + timedelta(days=30)).isoformat()))
                return True
            except Exception as e:
                print(f"[DB] insert_job failed: {e}")
                return False
        # memory fallback
        if any(j["url"] == job["url"] for j in self._mem_jobs):
            return False
        self._mem_jobs.append(job)
        return True

    async def recent_jobs(self, limit: int = 50) -> list[dict]:
        await self.init()
        if self._conn:
            try:
                rs = self._conn.execute(
                    "SELECT * FROM jobs ORDER BY first_seen DESC LIMIT ?", (limit,)
                )
                cols = [d[0] for d in rs.description]
                return [dict(zip(cols, r)) for r in rs.rows]
            except Exception:
                return []
        return self._mem_jobs[-limit:]

    async def log_run(self, strategy_id, started, finished, fetched, kept, errors):
        await self.init()
        if self._conn:
            try:
                self._conn.execute(
                    """INSERT INTO runs(strategy_id, started_at, finished_at,
                        fetched, kept, errors) VALUES(?,?,?,?,?,?)""",
                    (strategy_id, started, finished, fetched, kept, errors))
            except Exception:
                pass
        self._mem_runs.append(dict(strategy_id=strategy_id, fetched=fetched,
                                   kept=kept, errors=errors))

    async def log_failure(self, strategy_id, query, domain, etype, msg):
        await self.init()
        if self._conn:
            try:
                self._conn.execute(
                    """INSERT INTO failures(strategy_id, query, domain,
                        error_type, error_msg, created_at) VALUES(?,?,?,?,?,?)""",
                    (strategy_id, query, domain, etype, msg,
                     datetime.utcnow().isoformat()))
            except Exception:
                pass
        self._mem_fail.append(dict(query=query, domain=domain,
                                   error_type=etype, error_msg=msg))

    async def save_strategy(self, s: dict) -> int:
        await self.init()
        if self._conn:
            try:
                self._conn.execute("UPDATE strategies SET active=0")
                cur = self._conn.execute(
                    """INSERT INTO strategies(created_at, queries_json,
                        sources_json, reasoning, confidence, active)
                       VALUES(?,?,?,?,?,1)""",
                    (datetime.utcnow().isoformat(),
                     json.dumps(s.get("queries", [])),
                     json.dumps(s.get("sources", [])),
                     s.get("reasoning", ""), float(s.get("confidence", 0.5))))
                return int(cur.lastrowid or 0)
            except Exception:
                pass
        sid = len(self._mem_strat) + 1
        self._mem_strat.append({**s, "id": sid, "active": 1})
        return sid

    async def active_strategy(self) -> dict | None:
        await self.init()
        if self._conn:
            try:
                rs = self._conn.execute(
                    "SELECT * FROM strategies WHERE active=1 ORDER BY id DESC LIMIT 1")
                if rs.rows:
                    cols = [d[0] for d in rs.description]
                    row = dict(zip(cols, rs.rows[0]))
                    row["queries"] = json.loads(row.get("queries_json") or "[]")
                    row["sources"] = json.loads(row.get("sources_json") or "[]")
                    return row
            except Exception:
                return None
        for s in reversed(self._mem_strat):
            if s.get("active"):
                return s
        return None

    async def recent_failures(self, limit: int = 20) -> list[dict]:
        await self.init()
        if self._conn:
            try:
                rs = self._conn.execute(
                    "SELECT * FROM failures ORDER BY id DESC LIMIT ?", (limit,))
                cols = [d[0] for d in rs.description]
                return [dict(zip(cols, r)) for r in rs.rows]
            except Exception:
                return []
        return self._mem_fail[-limit:]

    async def recent_knowledge(self, limit: int = 50) -> list[dict]:
        await self.init()
        if self._conn:
            try:
                rs = self._conn.execute(
                    "SELECT id, question, answer, quality_score, created_at "
                    "FROM knowledge ORDER BY id DESC LIMIT ?", (limit,))
                cols = [d[0] for d in rs.description]
                return [dict(zip(cols, r)) for r in rs.rows]
            except Exception:
                return []
        return []

    async def insert_knowledge(self, q, a, score, model="gemini"):
        await self.init()
        if self._conn:
            try:
                self._conn.execute(
                    """INSERT INTO knowledge(question, answer, source_model,
                        quality_score, confidence, created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (q, a, model, float(score), float(score),
                     datetime.utcnow().isoformat()))
            except Exception:
                pass


DB_ENGINE = DB()

# ---------- Gemini client ----------
class Gemini:
    def __init__(self):
        self.calls = 0

    async def ask(self, system: str, user: str, *, engine=None) -> dict | None:
        """
        Hard pause guard: checks before AND after the network call.
        If engine is provided and paused mid-flight, discards the response.
        """
        if engine is not None and not engine.running:
            raise asyncio.CancelledError("paused before Gemini call")
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY missing")

        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": 0.4,
                "responseMimeType": "application/json",
            },
        }
        self.calls += 1
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as cx:
            r = await cx.post(GEMINI_URL, json=payload)
            r.raise_for_status()
            data = r.json()

        if engine is not None and not engine.running:
            raise asyncio.CancelledError("paused; discarding Gemini response")

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)
        except Exception as e:
            print(f"[Gemini] parse failed: {e}; raw={data}")
            # one retry, non-JSON
            return None


GEMINI = Gemini()

# ---------- Prompts ----------
STRATEGY_SYSTEM = """You refine a job-search strategy for a CIVIL ENGINEERING job
intelligence tool in EGYPT. Return ONLY valid JSON, no prose, no markdown.

HARD RULES:
- Only propose domains from ALLOWED_DOMAINS. Never invent a domain.
- Never propose CAPTCHA solving, proxies, fingerprint spoofing, or evasion.
- Enforce at least one change vs CURRENT_STRATEGY (new query, retire dead query,
  or new source mix).
- Retire any query that returned zero relevant results twice.
- Job must be posted in the last 7 days (relative to TODAY) and be located in
  Egypt (or explicitly Remote/Egypt). Title or description must match civil
  engineering.

OUTPUT JSON:
{
  "queries":   [str],       // 3-8 concrete search queries
  "sources":   [str],       // 1-6 domains from ALLOWED_DOMAINS
  "reasoning": str,         // <=120 words
  "confidence": float       // 0-1
}
"""

def strategy_user_prompt(today: str, current: dict | None,
                         failures: list[dict], allowed: list[str]) -> str:
    return json.dumps({
        "TODAY": today,
        "ALLOWED_DOMAINS": allowed,
        "CURRENT_STRATEGY": current or {},
        "RECENT_FAILURES": failures[:20],
    }, ensure_ascii=False, indent=2)


KNOWLEDGE_SYSTEM = """You are a civil-engineering research assistant for Egypt.
Answer the QUESTION concisely and accurately. Return ONLY JSON:
{"question": str, "answer": str, "confidence": float}
The answer must be useful to a civil engineer working in Egypt. If the question
cannot be answered factually, say so in `answer` and set confidence < 0.3.
"""

def knowledge_user_prompt(gaps: list[str], last_qs: list[str]) -> str:
    return json.dumps({
        "TASK": "Generate the single most valuable next question, then answer it.",
        "KNOWN_GAPS": gaps,
        "RECENT_QUESTIONS": last_qs[-15:],
        "BIAS": "Egypt civil engineering market, hiring, standards, codes, salaries.",
    }, ensure_ascii=False)


# ---------- HTML → plain text ----------
def html_to_text(html: str) -> str:
    try:
        return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html or "")


# ---------- Engine ----------
class Engine:
    def __init__(self, interval: float = CYCLE_SECONDS,
                 refine_every: int = REFINE_EVERY):
        self.interval = interval
        self.refine_every = refine_every
        self.running = False
        self.cycles = 0
        self.ai_calls = 0
        self.last_status = "idle"
        self.last_error: str | None = None
        self._task: asyncio.Task | None = None
        self._wake = asyncio.Event()
        self._gate = ComplianceGate()
        self._lock = asyncio.Lock()

    # ---------- controls ----------
    def start(self):
        if self.running:
            return
        self.running = True
        self.last_status = "running"
        self.last_error = None
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())
        else:
            self._wake.set()

    async def pause(self):
        if not self.running and self._task is None:
            self.last_status = "paused"
            return
        self.running = False
        self.last_status = "paused"
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        self._task = None

    # ---------- loop ----------
    async def _loop(self):
        try:
            while self.running:
                t0 = asyncio.get_event_loop().time()
                try:
                    await self._cycle()
                    self.cycles += 1
                    if self.last_status.startswith("error"):
                        self.last_status = "running"
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.last_error = f"{type(e).__name__}: {e}"
                    self.last_status = f"error: {self.last_error[:80]}"
                    traceback.print_exc()

                if not self.running:
                    break
                elapsed = asyncio.get_event_loop().time() - t0
                wait = max(0.0, self.interval - elapsed)
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=wait)
                    self._wake.clear()
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            self.last_status = "paused"
            raise

    # ---------- one cycle ----------
    async def _cycle(self):
        if not self.running:
            return
        async with self._lock:
            started = datetime.utcnow().isoformat()
            fetched = kept = errors = 0
            sid = None

            # --- strategy refinement every N cycles ---
            if self.cycles % self.refine_every == 0:
                sid = await self._refine_strategy()

            strategy = await DB_ENGINE.active_strategy()

            # --- knowledge pipeline ---
            if STATE.run_knowledge:
                try:
                    await self._knowledge_cycle()
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    errors += 1
                    await DB_ENGINE.log_failure(sid, "knowledge", "internal",
                                                type(e).__name__, str(e))

            # --- templates pipeline ---
            if STATE.run_templates:
                try:
                    f, k = await self._template_cycle(strategy, sid)
                    fetched += f
                    kept += k
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    errors += 1
                    await DB_ENGINE.log_failure(sid, "templates", "internal",
                                                type(e).__name__, str(e))

            await DB_ENGINE.log_run(sid, started,
                                    datetime.utcnow().isoformat(),
                                    fetched, kept, errors)

    # ---------- knowledge ----------
    async def _knowledge_cycle(self):
        if not self.running:
            return
        # build a light "gaps" signal from recent knowledge
        rows = await DB_ENGINE.recent_knowledge(limit=30)
        last_qs = [r.get("question") for r in rows]
        gaps = ["hiring standards Egypt",
                "common site roles Egypt",
                "salary ranges civil Egypt"]
        prompt = knowledge_user_prompt(gaps, last_qs)

        try:
            out = await GEMINI.ask(KNOWLEDGE_SYSTEM, prompt, engine=self)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            await DB_ENGINE.log_failure(None, "knowledge", "gemini",
                                        type(e).__name__, str(e))
            return
        self.ai_calls = GEMINI.calls
        if not out:
            return
        q = out.get("question"); a = out.get("answer"); c = out.get("confidence", 0.5)
        if q and a:
            await DB_ENGINE.insert_knowledge(q, a, c, model=GEMINI_MODEL)

    # ---------- strategy ----------
    async def _refine_strategy(self) -> int | None:
        if not self.running:
            return None
        current = await DB_ENGINE.active_strategy()
        fails = await DB_ENGINE.recent_failures(limit=20)
        allowed = list(self._gate.allowed_domains())
        user = strategy_user_prompt(
            datetime.utcnow().date().isoformat(), current, fails, allowed)
        try:
            out = await GEMINI.ask(STRATEGY_SYSTEM, user, engine=self)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            self.last_error = f"strategy: {e}"
            return None
        self.ai_calls = GEMINI.calls
        if not out:
            return None
        sid = await DB_ENGINE.save_strategy(out)
        return sid

    # ---------- template generation (uses strategy to fetch) ----------
    async def _template_cycle(self, strategy: dict | None, sid: int | None):
        if not strategy:
            return 0, 0
        fetched = kept = 0
        queries = strategy.get("queries", []) or []
        sources = strategy.get("sources", []) or []

        for domain in sources[:4]:
            if not self.running:
                break
            url = self._domain_to_url(domain, queries[:1])
            if not url:
                continue
            try:
                src = await self._gate.check(url, kind="fetch")
            except Blocked as e:
                await DB_ENGINE.log_failure(sid, queries[0] if queries else "",
                                            domain, "Blocked", str(e))
                continue

            try:
                async with httpx.AsyncClient(
                    timeout=HTTP_TIMEOUT,
                    headers={"User-Agent": USER_AGENT},
                ) as cx:
                    r = await cx.get(url)
                    r.raise_for_status()
                    html = r.text
                fetched += 1
            except Exception as e:
                await DB_ENGINE.log_failure(sid, queries[0] if queries else "",
                                            domain, type(e).__name__, str(e))
                continue

            for job in self._parse_jobs(html, url, src.tier):
                if not is_egypt_civil(job["title"] + " " + job["description_full"]):
                    continue
                if not within_7_days(job.get("posted_date")):
                    continue
                ok = await DB_ENGINE.insert_job(job)
                if ok:
                    kept += 1

        return fetched, kept

    def _domain_to_url(self, domain: str, queries: list[str]) -> str | None:
        """Very conservative default URLs. Extend per-domain as you verify."""
        domain = domain.lower().strip()
        q = (queries[0] if queries else "civil engineer egypt").replace(" ", "+")
        if domain == "arbeitnow.com":
            return "https://www.arbeitnow.com/api/job-board-api"
        if domain == "remoteok.com":
            return "https://remoteok.com/api"
        # Generic fallback is NOT safe — refuse unknown domains here.
        return None

    def _parse_jobs(self, html: str, url: str, tier: str) -> list[dict]:
        """
        Parse whatever the source returns into the canonical job dict.
        Extend per-domain. The generic branch extracts JSON APIs (common for Tier A).
        """
        jobs: list[dict] = []
        # try JSON first
        try:
            data = json.loads(html)
            items = data if isinstance(data, list) else data.get("data", [])
            for it in items if isinstance(items, list) else []:
                jobs.append(self._normalize(it, url, tier))
        except Exception:
            # fall back to HTML extraction
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.select("a[href]")[:200]:
                text = a.get_text(" ", strip=True)
                if not text or len(text) < 8:
                    continue
                jobs.append({
                    "title": text[:200],
                    "company": "",
                    "location": "Egypt",
                    "posted_date": None,
                    "url": a["href"] if a["href"].startswith("http")
                           else url,
                    "description_full": text,
                    "recruiter_name": None,
                    "recruiter_title": None,
                    "recruiter_contact": None,
                    "source_domain": url.split("/")[2],
                    "source_tier": tier,
                    "relevance_score": 0.0,
                    "quality_score": 0.0,
                })
        return jobs

    def _normalize(self, it: dict, url: str, tier: str) -> dict:
        desc = html_to_text(str(it.get("description") or it.get("body") or ""))
        return {
            "title": (it.get("title") or it.get("position") or "")[:300],
            "company": (it.get("company_name") or it.get("company") or "")[:200],
            "location": (it.get("location") or it.get("city") or "Egypt")[:200],
            "posted_date": it.get("created_at") or it.get("date") or it.get("posted_date"),
            "url": it.get("url") or it.get("apply_url") or url,
            "description_full": desc,
            "recruiter_name": None,
            "recruiter_title": None,
            "recruiter_contact": None,
            "source_domain": url.split("/")[2],
            "source_tier": tier,
            "relevance_score": 0.0,
            "quality_score": 0.0,
        }


# ---------- singleton ----------
engine = Engine()
