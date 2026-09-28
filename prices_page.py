# prices_page.py
# The Live Prices tab. Read + admin.

import asyncio
from nicegui import ui, app

import prices_db as _pdb
from prices_engine import prices_engine, auto_start_prices_if_needed
import prices_gemini as _pg


def _t(s):
    return s


def render_prices_page():
    state = {"cat": None, "region": None, "min_p": None, "max_p": None,
             "q": "", "admin_open": False}

    with ui.column().classes("w-full p-2 gap-3"):
        ui.label("Live Material Prices — Egypt").classes("hubx-title")
        ui.label("Self-learning crawler collecting construction material "
                 "prices from Egyptian sources.").classes("hubx-subtitle")

        # ---- stat row ----
        with ui.row().classes("gap-3 flex-wrap"):
            stats_labels = {}
            for key, label in [("observations", "Observations"),
                                ("pending", "Pending"),
                                ("approved", "Approved"),
                                ("materials", "Materials"),
                                ("categories", "Categories"),
                                ("regions", "Regions")]:
                with ui.column().classes("hubx-stat items-start gap-0"):
                    ui.label(label).classes("hubx-stat-label")
                    stats_labels[key] = ui.label("0").classes("hubx-stat-value")

        # ---- Admin controls ----
        with ui.card().classes("hubx-card w-full"):
            ui.label("Crawler controls").classes("font-bold text-base mb-2")
            with ui.row().classes("gap-2 flex-wrap items-center"):
                status_badge = ui.badge("idle", color="grey").classes("text-sm")

                async def do_start():
                    await prices_engine.start(by_user=True)
                    await refresh_all()
                async def do_pause():
                    await prices_engine.pause()
                    await refresh_all()
                async def do_one():
                    try:
                        await prices_engine._cycle()
                        ui.notify("Cycle complete.", color="green")
                    except Exception as e:
                        ui.notify(f"Cycle failed: {e}", color="red")
                    await refresh_all()

                ui.button("▶ Start crawler", on_click=do_start).classes(
                    "hubx-btn hubx-btn-accent")
                ui.button("⏸ Pause", on_click=do_pause).classes(
                    "hubx-btn hubx-btn-warn")
                ui.button("▶ Run one cycle now", on_click=do_one).classes(
                    "hubx-btn hubx-btn-primary")

            debug_label = ui.label("").style(
                "color:var(--hubx-text-dim);font-size:0.85rem")
            err_label = ui.label("").style("color:#ffc270;font-size:0.85rem")

        # ---- Add source + Seed ----
        with ui.card().classes("hubx-card w-full"):
            ui.label("Sources").classes("font-bold text-base mb-2")
            with ui.row().classes("gap-2 flex-wrap items-center w-full"):
                name_in = ui.input(label="Name").classes("flex-1").props("dense")
                url_in = ui.input(label="URL").classes("flex-1").props("dense")

                def add_src():
                    ok = _pdb.add_source(name_in.value, url_in.value, "html")
                    if ok:
                        ui.notify("Source added", color="green")
                        name_in.value = ""
                        url_in.value = ""
                    else:
                        ui.notify("Source exists or invalid", color="orange")
                    refresh_all()

                def seed_now():
                    from prices_sources import SEED_PRICE_SOURCES
                    added = 0
                    for nm, u, k in SEED_PRICE_SOURCES:
                        if _pdb.add_source(nm, u, k):
                            added += 1
                    ui.notify(f"Seeded {added} sources", color="green")
                    refresh_all()

                ui.button("+ Add source", on_click=add_src).classes(
                    "hubx-btn hubx-btn-primary")
                ui.button("Seed Egyptian sources", on_click=seed_now).classes(
                    "hubx-btn hubx-btn-accent")

            src_table = ui.table(columns=[
                {"name": "name", "label": "Name", "field": "name", "align": "left"},
                {"name": "url", "label": "URL", "field": "url", "align": "left"},
                {"name": "status", "label": "Last status", "field": "status"},
                {"name": "when", "label": "Last run", "field": "when"},
                {"name": "actions", "label": "", "field": "actions"},
            ], rows=[]).classes("w-full mt-2")

            def _del(sid):
                _pdb.delete_source(sid)
                ui.notify("Deleted", color="orange")
                refresh_all()

        # ---- Filters ----
        with ui.card().classes("hubx-card w-full"):
            ui.label("Filters").classes("font-bold text-base mb-2")
            with ui.row().classes("gap-2 flex-wrap items-end w-full"):
                q_in = ui.input(label="Search material").classes("flex-1").props("dense")
                cat_sel = ui.select(options={}, label="Category", with_input=True).classes("w-52").props("dense")
                reg_sel = ui.select(options={}, label="Region", with_input=True).classes("w-52").props("dense")
                min_in = ui.number(label="Min price", value=None).classes("w-32").props("dense")
                max_in = ui.number(label="Max price", value=None).classes("w-32").props("dense")

                def apply():
                    state["q"] = (q_in.value or "").strip()
                    state["cat"] = cat_sel.value
                    state["region"] = reg_sel.value
                    state["min_p"] = min_in.value
                    state["max_p"] = max_in.value
                    refresh_table()

                def reset():
                    q_in.value = ""
                    cat_sel.value = None
                    reg_sel.value = None
                    min_in.value = None
                    max_in.value = None
                    apply()

                ui.button("Apply", on_click=apply).classes(
                    "hubx-btn hubx-btn-primary")
                ui.button("Reset", on_click=reset).classes(
                    "hubx-btn hubx-btn-ghost")

        # ---- Results table ----
        with ui.card().classes("hubx-card w-full"):
            ui.label("Results").classes("font-bold text-base mb-2")
            results_table = ui.table(columns=[
                {"name": "material", "label": "Material", "field": "material",
                 "align": "left"},
                {"name": "spec", "label": "Spec", "field": "spec"},
                {"name": "category", "label": "Category", "field": "category"},
                {"name": "region", "label": "Region", "field": "region"},
                {"name": "low", "label": "Low", "field": "low"},
                {"name": "avg", "label": "Avg", "field": "avg"},
                {"name": "high", "label": "High", "field": "high"},
                {"name": "unit", "label": "Unit", "field": "unit"},
                {"name": "conf", "label": "Conf", "field": "conf"},
                {"name": "n", "label": "N", "field": "n"},
            ], rows=[]).classes("w-full mt-2")

        # ---- Pending observations ----
        with ui.card().classes("hubx-card w-full"):
            ui.label("Recent observations (pending approval)").classes(
                "font-bold text-base mb-2")
            obs_table = ui.table(columns=[
                {"name": "material", "label": "Material", "field": "material",
                 "align": "left"},
                {"name": "price", "label": "Price", "field": "price"},
                {"name": "unit", "label": "Unit", "field": "unit"},
                {"name": "region", "label": "Region", "field": "region"},
                {"name": "source", "label": "Source", "field": "source"},
                {"name": "status", "label": "Status", "field": "status"},
                {"name": "actions", "label": "", "field": "actions"},
            ], rows=[]).classes("w-full mt-2")

            def _approve(oid):
                _pdb.approve_observation(oid)
                ui.notify("Approved", color="green")
                refresh_all()

            def _reject(oid):
                _pdb.reject_observation(oid)
                ui.notify("Rejected", color="orange")
                refresh_all()

            def _delete(oid):
                _pdb.delete_observation(oid)
                ui.notify("Deleted", color="orange")
                refresh_all()

        # ---- Refresh functions ----
        def _sources_sync():
            rows = _pdb.list_sources(200)
            return [{
                "id": r[0], "name": r[1], "url": r[2], "kind": r[3],
                "active": r[4], "when": (r[5] or "")[:19],
                "status": r[6] or "—",
            } for r in rows]

        def _prices_sync():
            return _pdb.search_prices(
                query=state["q"],
                category_id=state["cat"],
                region_id=state["region"],
                min_price=state["min_p"],
                max_price=state["max_p"],
                limit=300)

        def _obs_sync():
            return _pdb.recent_observations(50)

        def refresh_table():
            rows = _prices_sync()
            results_table.rows = [{
                "material": r[1], "spec": r[2] or "",
                "category": r[4] or "—", "region": r[5] or "—",
                "low": f"{r[6]:.0f}" if r[6] is not None else "—",
                "avg": f"{r[7]:.0f}" if r[7] is not None else "—",
                "high": f"{r[8]:.0f}" if r[8] is not None else "—",
                "unit": r[3] or "",
                "conf": f"{r[9]:.2f}" if r[9] is not None else "—",
                "n": r[10] or 0,
            } for r in rows]

        def refresh_categories():
            cats = _pdb.all_categories()
            opts = {c[0]: c[2] for c in cats}
            cat_sel.options = opts
            cat_sel.update()

        def refresh_regions():
            regs = _pdb.all_regions()
            opts = {r[0]: r[1] for r in regs}
            reg_sel.options = opts
            reg_sel.update()

        async def refresh_all():
            # stats
            st = prices_engine.stats()
            for k in stats_labels:
                stats_labels[k].text = str(st.get(k, 0))
            status_badge.text = st["last_status"]
            status_badge.props(
                f'color={"green" if not prices_engine.paused else "orange"}')
            debug_label.text = st["last_debug"]
            err_label.text = (f"AI: {_pg.last_error}"
                              if _pg.last_error else "")

            # sources
            src_rows = await asyncio.to_thread(_sources_sync)
            src_table.rows = [{
                "name": r["name"], "url": r["url"],
                "status": r["status"], "when": r["when"],
                "actions": "",
            } for r in src_rows]

            # categories/regions
            await asyncio.to_thread(refresh_categories)
            await asyncio.to_thread(refresh_regions)

            # prices + observations
            await asyncio.to_thread(refresh_table)
            obs_rows = await asyncio.to_thread(_obs_sync)
            obs_table.rows = [{
                "material": r[1] or "?",
                "price": f"{r[3]:.0f} {r[4]}" if r[3] is not None else "—",
                "unit": r[5] or "—",
                "region": r[6] or "—",
                "source": r[7] or "—",
                "status": ("✅ approved" if r[9]
                           else "❌ rejected" if r[10] else "⏳ pending"),
                "actions": "",
            } for r in obs_rows]

        # initial + auto refresh
        ui.timer(0.1, refresh_all, once=True)
        ui.timer(45.0, refresh_all)
