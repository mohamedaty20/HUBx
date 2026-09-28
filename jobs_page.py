# jobs_page.py — HUBx Job Board Scraper
# The Render admin panel for the jobs engine. Reached at /jobs.

import asyncio
from nicegui import ui

import jobs_db as _jdb
from jobs_engine import jobs_engine, auto_start_jobs_if_needed
import jobs_gemini as _jg


def render_jobs_page():
    state = {"admin_open": True}

    with ui.column().classes("w-full p-2 gap-3"):
        ui.label("Job Board Scraper — Engine").classes("hubx-title")
        ui.label("Scrapes ONLY the URLs you enter below. Groq summarizes "
                 "each posting and stores it in D1 for the public Jobs tab."
                 ).classes("hubx-subtitle")

        # ── stat strip ────────────────────────────────────────────────
        with ui.row().classes("gap-3 flex-wrap"):
            stat_labels = {}
            for key, label in [
                ("cycles", "Cycles"),
                ("calls", "Groq Calls"),
                ("jobs_scraped", "Scraped"),
                ("postings", "Postings"),
                ("companies", "Companies"),
                ("sources_active", "Active Sources"),
            ]:
                with ui.column().classes("hubx-stat items-start gap-0"):
                    ui.label(label).classes("hubx-stat-label")
                    stat_labels[key] = ui.label("0").classes(
                        "hubx-stat-value")

        # ── controls ──────────────────────────────────────────────────
        with ui.card().classes("hubx-card w-full"):
            ui.label("Engine controls").classes("font-bold text-base mb-2")
            with ui.row().classes("gap-2 flex-wrap items-center"):
                status_badge = ui.badge("idle", color="grey").classes("text-sm")

                async def do_start():
                    await jobs_engine.start(by_user=True)
                    await refresh_all()

                async def do_pause():
                    await jobs_engine.pause()
                    await refresh_all()

                async def do_one():
                    try:
                        await jobs_engine._cycle()
                        ui.notify("Cycle complete.", color="green")
                    except Exception as e:
                        ui.notify(f"Cycle failed: {e}", color="red")
                    await refresh_all()

                ui.button("▶ Start engine", on_click=do_start).classes(
                    "hubx-btn hubx-btn-accent")
                ui.button("⏸ Stop engine", on_click=do_pause).classes(
                    "hubx-btn hubx-btn-warn")
                ui.button("▶ Run one cycle now", on_click=do_one).classes(
                    "hubx-btn hubx-btn-primary")

            debug_label = ui.label("").style(
                "color:var(--hubx-text-dim);font-size:0.85rem")
            err_label = ui.label("").style(
                "color:#ffc270;font-size:0.85rem")
            cooldown_label = ui.label("").style(
                "color:#ffc270;font-size:0.85rem")

        # ── add source ────────────────────────────────────────────────
        with ui.card().classes("hubx-card w-full"):
            ui.label("Job sources").classes("font-bold text-base mb-2")
            ui.label("Enter the LIST page URL (the page that shows "
                     "multiple job postings). The engine collects the "
                     "individual posting links itself."
                     ).classes("text-xs mb-2").style(
                "color:var(--hubx-text-dim)")

            with ui.row().classes("gap-2 flex-wrap items-center w-full"):
                name_in = ui.input(label="Company name").classes(
                    "flex-1").props("dense")
                url_in = ui.input(label="List page URL").classes(
                    "flex-1").props("dense")
                kind_sel = ui.select(
                    options={"html": "Static HTML (httpx)",
                             "js": "JavaScript (Playwright)"},
                    value="html", label="Kind").classes("w-56").props(
                    "dense")

                def add_src():
                    ok = _jdb.add_source(
                        name_in.value, url_in.value, kind_sel.value)
                    if ok:
                        ui.notify("Source added", color="green")
                        name_in.value = ""
                        url_in.value = ""
                    else:
                        ui.notify("Source exists or invalid", color="orange")
                    refresh_all()

                ui.button("+ Add source", on_click=add_src).classes(
                    "hubx-btn hubx-btn-primary")

            src_table = ui.table(columns=[
                {"name": "id", "label": "ID", "field": "id"},
                {"name": "name", "label": "Company", "field": "name",
                 "align": "left"},
                {"name": "url", "label": "URL", "field": "url",
                 "align": "left"},
                {"name": "kind", "label": "Kind", "field": "kind"},
                {"name": "active", "label": "Active", "field": "active"},
                {"name": "when", "label": "Last run", "field": "when"},
                {"name": "status", "label": "Last status",
                 "field": "status"},
                {"name": "actions", "label": "", "field": "actions"},
            ], rows=[]).classes("w-full mt-2")

            def _toggle(sid):
                _jdb.toggle_source(sid)
                ui.notify("Toggled", color="primary")
                refresh_all()

            def _delete(sid):
                _jdb.delete_source(sid)
                ui.notify("Deleted", color="orange")
                refresh_all()

        # ── recent postings ───────────────────────────────────────────
        with ui.card().classes("hubx-card w-full"):
            ui.label("Recent postings").classes("font-bold text-base mb-2")
            postings_table = ui.table(columns=[
                {"name": "id", "label": "ID", "field": "id"},
                {"name": "title", "label": "Title", "field": "title",
                 "align": "left"},
                {"name": "company", "label": "Company",
                 "field": "company", "align": "left"},
                {"name": "location", "label": "Location",
                 "field": "location"},
                {"name": "posted", "label": "Posted", "field": "posted"},
                {"name": "scraped", "label": "Scraped",
                 "field": "scraped"},
                {"name": "actions", "label": "", "field": "actions"},
            ], rows=[]).classes("w-full mt-2")

            def _del_posting(pid):
                _jdb.delete_posting(pid)
                ui.notify("Deleted", color="orange")
                refresh_all()

        # ── danger zone ───────────────────────────────────────────────
        with ui.card().classes("hubx-card w-full"):
            ui.label("Danger zone").classes("font-bold text-base mb-2")
            ui.label("Delete every job posting (sources are kept)."
                     ).classes("text-xs mb-2").style(
                "color:var(--hubx-text-dim)")

            def reset_postings():
                _jdb.reset_postings()
                ui.notify("Postings cleared", color="orange")
                refresh_all()

            ui.button("🗑 Reset postings table",
                      on_click=reset_postings).classes(
                "hubx-btn hubx-btn-danger")

        # ── refresh ───────────────────────────────────────────────────
        def _sources_sync():
            rows = _jdb.list_sources(200)
            return [{
                "id": r[0], "name": r[1], "url": r[2], "kind": r[3],
                "active": "✅" if r[4] else "—",
                "when": (r[5] or "")[:19],
                "status": r[6] or "—",
            } for r in rows]

        def _postings_sync():
            rows = _jdb.recent_postings(50)
            return [{
                "id": r[0], "title": r[1] or "",
                "company": r[2] or "", "location": r[3] or "",
                "posted": r[4] or "", "scraped": (r[6] or "")[:19],
            } for r in rows]

        async def refresh_all():
            st = jobs_engine.stats()
            for k in stat_labels:
                stat_labels[k].text = str(st.get(k, 0))
            status_badge.text = st["last_status"]
            status_badge.props(
                f'color={"green" if not jobs_engine.paused else "orange"}')
            debug_label.text = st["last_debug"]
            err_label.text = (f"AI: {_jg.last_error}"
                              if _jg.last_error else "")
            cd = st.get("cooldown_left", 0)
            if cd > 0:
                m = cd // 60
                s = cd % 60
                cooldown_label.text = f"⏳ Groq cooldown: {m}m {s}s"
            else:
                cooldown_label.text = ""

            src_rows = await asyncio.to_thread(_sources_sync)
            src_table.rows = src_rows

            post_rows = await asyncio.to_thread(_postings_sync)
            postings_table.rows = post_rows

        ui.timer(0.1, refresh_all, once=True)
        ui.timer(30.0, refresh_all)
