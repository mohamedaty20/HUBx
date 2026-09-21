# main.py
# NiceGUI app: home, dashboards, manual paste.
# Binds to 0.0.0.0:$PORT as Render requires.

import os
import asyncio
import datetime
from collections import Counter

from nicegui import ui, app

from db import init_db, get_jobs, insert_job
from engine import engine
from sources import MANUAL_PASTE_DOMAINS, get_tier

PORT = int(os.getenv("PORT", "8080"))

init_db()


def _render_header():
    with ui.header().classes("items-center justify-between"):
        ui.label("HUBx").classes("text-xl font-bold")
        with ui.row():
            ui.link("Home", "/").classes("text-white")
            ui.link("Dashboards", "/dashboards").classes("text-white")
            ui.link("Manual Paste", "/paste").classes("text-white")


async def _keepalive():
    while True:
        await asyncio.sleep(600)
        try:
            import httpx
            base = os.getenv("RENDER_EXTERNAL_URL", f"http://localhost:{PORT}")
            async with httpx.AsyncClient(timeout=10) as c:
                await c.get(base)
        except Exception:
            pass


app.on_startup(lambda: asyncio.create_task(_keepalive()))


@ui.page("/")
def home():
    _render_header()
    ui.label("HUBx - Civil Engineering Jobs (Egypt)").classes(
        "text-3xl font-bold")

    with ui.row().classes("gap-4 items-center mt-2"):
        status_badge = ui.badge("idle", color="grey")
        cycles_label = ui.label("Cycles: 0")
        gemini_label = ui.label("Gemini calls: 0")
        error_label = ui.label("").classes("text-red-500")

    async def refresh_status():
        status_badge.text = engine.last_status
        status_badge.props(
            f'color={"green" if not engine.paused else "orange"}')
        cycles_label.text = f"Cycles: {engine.cycles_completed}"
        gemini_label.text = f"Gemini calls: {engine.gemini_calls}"
        error_label.text = engine.last_error[:200]

    async def do_start():
        await engine.start()
        await refresh_status()

    async def do_pause():
        await engine.pause()
        await refresh_status()

    with ui.row().classes("gap-2 mt-4"):
        ui.button("Start", on_click=do_start).props("color=green")
        ui.button("Pause", on_click=do_pause).props("color=orange")

    with ui.row().classes("gap-2 mt-4"):
        loc_filter = ui.input("Location filter").props("dense outlined")
        from_filter = ui.input("From (YYYY-MM-DD)").props("dense outlined")
        to_filter = ui.input("To (YYYY-MM-DD)").props("dense outlined")

    table = ui.table(
        columns=[
            {"name": "title", "label": "Title",
             "field": "title", "align": "left"},
            {"name": "company", "label": "Company", "field": "company"},
            {"name": "location", "label": "Location", "field": "location"},
            {"name": "posted_date", "label": "Posted",
             "field": "posted_date"},
            {"name": "source_domain", "label": "Source",
             "field": "source_domain"},
        ],
        rows=[],
    ).classes("mt-4 w-full")

    def load_jobs():
        rows = get_jobs(
            limit=200,
            date_from=from_filter.value or None,
            date_to=to_filter.value or None,
            location=loc_filter.value or None,
        )
        table.rows = [
            {
                "title": r[1], "company": r[2], "location": r[3],
                "posted_date": r[4], "source_domain": r[10],
            }
            for r in rows
        ]

    ui.button("Apply filters", on_click=load_jobs)
    load_jobs()

    ui.timer(2.0, refresh_status)


@ui.page("/dashboards")
def dashboards():
    _render_header()
    ui.label("Dashboards").classes("text-2xl font-bold")
    rows = get_jobs(limit=1000)

    weeks = Counter()
    for r in rows:
        try:
            d = datetime.date.fromisoformat((r[4] or "")[:10])
            weeks[d.isocalendar()[1]] += 1
        except Exception:
            pass
    with ui.card().classes("mt-4 w-full"):
        ui.label("Jobs per week")
        ui.echart({
            "xAxis": {"type": "category",
                      "data": [str(k) for k in sorted(weeks)]},
            "yAxis": {"type": "value"},
            "series": [{"data": [weeks[k] for k in sorted(weeks)],
                        "type": "bar"}],
        }).classes("h-64 w-full")

    comps = Counter(r[2] for r in rows if r[2])
    with ui.card().classes("mt-4 w-full"):
        ui.label("Top companies")
        ui.echart({
            "xAxis": {"type": "category",
                      "data": [c for c, _ in comps.most_common(10)]},
            "yAxis": {"type": "value"},
            "series": [{"data": [n for _, n in comps.most_common(10)],
                        "type": "bar"}],
        }).classes("h-64 w-full")

    locs = Counter(r[3] for r in rows if r[3])
    with ui.card().classes("mt-4 w-full"):
        ui.label("Top locations")
        ui.echart({
            "xAxis": {"type": "category",
                      "data": [l for l, _ in locs.most_common(10)]},
            "yAxis": {"type": "value"},
            "series": [{"data": [n for _, n in locs.most_common(10)],
                        "type": "bar"}],
        }).classes("h-64 w-full")

    srcs = Counter(r[10] for r in rows if r[10])
    with ui.card().classes("mt-4 w-full"):
        ui.label("Source mix")
        ui.echart({
            "series": [{"type": "pie", "data": [
                {"name": s, "value": n} for s, n in srcs.most_common()]}],
        }).classes("h-64 w-full")

    scores = [r[12] for r in rows if r[12] is not None]
    with ui.card().classes("mt-4 w-full"):
        ui.label("Relevance-score distribution")
        bins = Counter(int(s * 10) / 10 for s in scores)
        ui.echart({
            "xAxis": {"type": "category",
                      "data": [str(k) for k in sorted(bins)]},
            "yAxis": {"type": "value"},
            "series": [{"data": [bins[k] for k in sorted(bins)],
                        "type": "bar"}],
        }).classes("h-64 w-full")

    with ui.card().classes("mt-4 w-full"):
        ui.label("Open strategy questions")
        ui.markdown("""
- Which additional Tier A/B domains produce Egypt civil-eng jobs?
- Are recruiter details appearing verbatim in any postings?
- Should we retire queries with zero relevant results twice?
- Is the 7-day window catching enough fresh postings?
        """)


@ui.page("/paste")
def manual_paste():
    _render_header()
    ui.label("Manual Paste (Tier C sites)").classes("text-2xl font-bold")

    domain = ui.select(MANUAL_PASTE_DOMAINS, label="Domain").classes("w-64")
    text = ui.textarea("Paste job text or HTML here").classes(
        "w-full h-64")
    preview_table = ui.table(
        columns=[
            {"name": "title", "label": "Title", "field": "title"},
            {"name": "company", "label": "Company", "field": "company"},
            {"name": "location", "label": "Location", "field": "location"},
        ],
        rows=[],
    ).classes("mt-4 w-full")

    parsed = {"rows": []}

    def do_parse():
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text.value or "", "html.parser")
        plain = soup.get_text("\n", strip=True)
        parsed["rows"] = [{
            "title": plain.split("\n")[0][:120],
            "company": "",
            "location": "Egypt",
            "description_full": plain,
            "source_domain": domain.value,
            "source_tier": get_tier(domain.value),
            "posted_date": datetime.date.today().isoformat(),
        }]
        preview_table.rows = [
            {"title": p["title"], "company": p["company"],
             "location": p["location"]} for p in parsed["rows"]]

    def do_store():
        for p in parsed["rows"]:
            insert_job(p)
        ui.notify(f"Stored {len(parsed['rows'])} record(s).")

    ui.button("Parse", on_click=do_parse)
    ui.button("Confirm & Store", on_click=do_store).props("color=green")


ui.run(host="0.0.0.0", port=PORT, reload=False, title="HUBx")
