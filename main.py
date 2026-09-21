# main.py
import os
import asyncio
import tempfile
from collections import Counter

from nicegui import ui, app

from db import (init_db, get_all_knowledge, get_knowledge_by_id,
                save_check_report, recent_check_reports,
                recent_learning_runs, knowledge_stats, db_health,
                category_counts, confidence_bins, version_counts,
                runs_per_cycle)
from engine import engine
from file_reader import extract_text
from gemini import check_document
import gemini as gemini_mod
from report_builder import build_txt, build_pdf, build_xlsx

PORT = int(os.getenv("PORT", "8080"))

init_db()


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

# Global CSS: bigger markdown headings.
ui.add_head_html("""
<style>
.knowledge-detail h1 { font-size: 2.2rem; font-weight: 800;
                       margin: 0.4em 0 0.6em 0; line-height: 1.2; }
.knowledge-detail h2 { font-size: 1.6rem; font-weight: 700;
                       margin: 0.8em 0 0.4em 0; }
.knowledge-detail h3 { font-size: 1.25rem; font-weight: 700;
                       margin: 0.6em 0 0.3em 0; }
.knowledge-detail p  { font-size: 1.05rem; line-height: 1.65;
                       margin: 0.4em 0; }
.knowledge-detail ul { margin: 0.3em 0 0.6em 1.2em; }
.knowledge-detail li { font-size: 1.02rem; line-height: 1.55;
                       margin: 0.2em 0; }
.knowledge-detail strong { font-weight: 700; }
.hubx-topic-btn { font-size: 1rem; font-weight: 600;
                  text-align: left; padding: 8px 10px; }
.hubx-cat-btn { font-size: 1.05rem; font-weight: 700;
                text-align: left; padding: 8px 10px; }
.hubx-cat-btn-selected { background: #1976d2 !important;
                         color: white !important; }
</style>
""")


def _header():
    with ui.header().classes("items-center justify-between"):
        ui.label("HUBx v2 — Civil Quality Engineering").classes(
            "text-lg font-bold")
        with ui.row():
            ui.link("Check Document", "/").classes("text-white")
            ui.link("Knowledge", "/knowledge").classes("text-white")
            ui.link("Charts", "/charts").classes("text-white")
            ui.link("Dashboard", "/dashboard").classes("text-white")


def _db_banner():
    h = db_health()
    if h["mode"] == "local":
        with ui.row().classes(
                "bg-orange-100 text-orange-900 p-2 rounded w-full "
                "items-center gap-2"):
            ui.icon("warning")
            ui.label(
                "Running on LOCAL SQLite — data will be lost on every "
                "redeploy. Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN "
                "in Render's Environment tab."
            )
    elif h["mode"] == "turso":
        with ui.row().classes(
                "bg-green-50 text-green-800 p-1 rounded w-full "
                "items-center gap-2"):
            ui.icon("cloud_done")
            ui.label(f"Connected to Turso: {h['connection']}")


# =================================================================
# Check Document
# =================================================================

@ui.page("/")
def check_page():
    _header()
    _db_banner()
    ui.label("Engineering Document Review").classes(
        "text-3xl font-bold mt-2")
    ui.label(
        "Upload a PDF, TXT, XLSX, PNG or JPG. The AI checks it against "
        "Egyptian codes (ECP 203/205/202) and lists every mistake with a fix."
    ).classes("text-gray-600 mb-4 text-lg")

    state = {"result": {}, "filename": "", "original_text": ""}

    issues_table = ui.table(
        columns=[
            {"name": "severity", "label": "Severity", "field": "severity"},
            {"name": "location", "label": "Location", "field": "location"},
            {"name": "problem", "label": "Problem", "field": "problem"},
            {"name": "fix", "label": "Fix", "field": "fix"},
            {"name": "reference", "label": "Reference", "field": "reference"},
        ],
        rows=[],
    ).classes("w-full mt-4")

    summary_box = ui.markdown("").classes("mt-2 knowledge-detail")
    score_label = ui.label("").classes("text-2xl font-bold mt-2")
    err_label = ui.label("").classes("text-red-500")

    async def handle_upload(e):
        data = await e.content.read()
        filename = e.name or "upload"
        ext = os.path.splitext(filename)[1].lower()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(data)
        tmp.close()

        ui.notify(f"Reading {filename}…")
        text, ftype = await extract_text(tmp.name, filename)
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

        if not text.strip():
            ui.notify(f"No text extracted from {filename} "
                      f"(type={ftype}).", color="orange")
            return

        state["filename"] = filename
        state["original_text"] = text

        ui.notify("Analysing with Gemini…")
        result = await check_document(filename, ftype, text)
        if not result:
            err_label.text = f"Gemini error: {gemini_mod.last_error}"
            ui.notify("Gemini returned no result.", color="red")
            return
        err_label.text = ""

        state["result"] = result
        score = float(result.get("score", 0.0))
        score_label.text = f"Score: {score:.2f} / 1.00"
        score_label.classes(
            replace="text-2xl font-bold mt-2 " +
            ("text-green-600" if score >= 0.7 else "text-red-600"))
        summary_box.content = result.get("summary", "")
        issues_table.rows = result.get("issues", []) or []

        try:
            save_check_report(filename, ftype, text,
                              result.get("issues", []), score,
                              result.get("summary", ""))
        except Exception as ex:
            ui.notify(f"Could not save report: {ex}", color="orange")

        ui.notify(f"Found {len(result.get('issues', []))} issue(s).")

    ui.upload(on_upload=handle_upload,
              auto_upload=True,
              max_file_size=20_000_000,
              multiple=False).classes("w-full")

    ui.label("Result").classes("text-2xl font-bold mt-6")
    score_label
    summary_box
    issues_table
    err_label

    def dl_txt():
        if not state["result"]:
            ui.notify("Upload a file first.", color="orange"); return
        ui.download(build_txt(state["filename"], state["result"]),
                    filename="hubx_report.txt")

    def dl_pdf():
        if not state["result"]:
            ui.notify("Upload a file first.", color="orange"); return
        ui.download(build_pdf(state["filename"], state["result"]),
                    filename="hubx_report.pdf")

    def dl_xlsx():
        if not state["result"]:
            ui.notify("Upload a file first.", color="orange"); return
        ui.download(build_xlsx(state["filename"], state["result"]),
                    filename="hubx_report.xlsx")

    with ui.row().classes("gap-2 mt-4"):
        ui.button("Download TXT", on_click=dl_txt)
        ui.button("Download PDF", on_click=dl_pdf).props("color=red")
        ui.button("Download XLSX", on_click=dl_xlsx).props("color=green")


# =================================================================
# Knowledge (fixed category filter)
# =================================================================

@ui.page("/knowledge")
def knowledge_page():
    _header()
    _db_banner()
    ui.label("Self-Learned Civil Quality Knowledge").classes(
        "text-3xl font-bold mt-2")

    status_bar = ui.label("").classes(
        "text-sm text-gray-600 bg-gray-100 p-2 rounded w-full mt-1")

    # Tracks the currently selected category across refreshes.
    selected = {"cat": None}

    with ui.row().classes("w-full gap-4 mt-3 no-wrap"):
        with ui.card().classes("w-80 shrink-0 h-[75vh] overflow-auto"):
            ui.label("Categories").classes("text-xl font-bold")
            cat_container = ui.column().classes("w-full gap-1 mt-2")
            ui.separator()
            ui.label("Topics").classes("text-xl font-bold mt-3")
            topic_label = ui.label("").classes(
                "text-sm text-gray-500 mb-1")
            topic_container = ui.column().classes("w-full gap-1")

        with ui.card().classes("flex-1 h-[75vh] overflow-auto"):
            detail = ui.markdown("").classes(
                "knowledge-detail whitespace-pre-wrap")

    def show_item(kid: int):
        k = get_knowledge_by_id(kid)
        if not k:
            return
        body = k[4] or k[3] or "(empty)"
        detail.content = (
            f"# {k[1]}\n\n"
            f"**Category:** {k[2]} &nbsp;|&nbsp; "
            f"**Version:** {k[5]} &nbsp;|&nbsp; "
            f"**Confidence:** {round(k[6] or 0, 2)}\n\n"
            f"*Created: {k[7]} · Updated: {k[8]}*\n\n"
            f"---\n\n{body}"
        )

    def render_topics():
        topic_container.clear()
        cat = selected["cat"]
        rows = get_all_knowledge(category=cat, limit=1000)
        topic_label.text = (
            f"showing: {cat}" if cat else f"showing: all ({len(rows)})"
        )
        with topic_container:
            if not rows:
                ui.label("(no topics in this category yet)").classes(
                    "text-gray-400 italic p-2")
            for r in rows[:300]:
                kid = r[0]
                topic = r[1]
                ver = r[5]
                ui.button(
                    f"{topic[:50]}  ·  v{ver}",
                    on_click=lambda k=kid: show_item(k),
                ).props("flat dense align=left no-caps").classes(
                    "hubx-topic-btn w-full justify-start")

    def render_categories():
        cat_container.clear()
        counts = category_counts()
        with cat_container:
            is_all = selected["cat"] is None
            all_btn = ui.button("Show all topics").props(
                "flat dense align=left no-caps"
            ).classes(
                "hubx-cat-btn w-full justify-start"
                + (" hubx-cat-btn-selected" if is_all else ""))
            all_btn.on("click", lambda: select_category(None))

            for cat, n in counts:
                is_sel = (selected["cat"] == cat)
                btn = ui.button(f"{cat}  ({n})").props(
                    "flat dense align=left no-caps"
                ).classes(
                    "hubx-cat-btn w-full justify-start"
                    + (" hubx-cat-btn-selected" if is_sel else ""))
                btn.on("click", lambda c=cat: select_category(c))

    def select_category(cat):
        selected["cat"] = cat
        render_categories()
        render_topics()

    def refresh_all():
        try:
            s = knowledge_stats()
            status_bar.text = (
                f"Knowledge rows: {s['total']}  |  Refined: {s['refined']}"
            )
        except Exception as ex:
            status_bar.text = f"DB error: {ex}"
        render_categories()
        render_topics()

    refresh_all()
    ui.timer(5.0, refresh_all)


# =================================================================
# Charts (matplotlib)
# =================================================================

@ui.page("/charts")
def charts_page():
    _header()
    _db_banner()
    ui.label("Interactive Charts").classes("text-3xl font-bold mt-2")
    ui.label(
        "Live charts built from self-learned knowledge and learning runs. "
        "They update automatically as the engine refines its data."
    ).classes("text-gray-600 mb-4")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with ui.row().classes("w-full gap-4 flex-wrap"):
        c1 = ui.matplotlib(figsize=(6, 4)).classes(
            "w-[48%] h-80 bg-white rounded p-2")
        c2 = ui.matplotlib(figsize=(6, 4)).classes(
            "w-[48%] h-80 bg-white rounded p-2")
        c3 = ui.matplotlib(figsize=(10, 4)).classes(
            "w-full h-80 bg-white rounded p-2")
        c4 = ui.matplotlib(figsize=(10, 4)).classes(
            "w-full h-80 bg-white rounded p-2")

    def draw_cat(fig):
        fig.clear()
        ax = fig.add_subplot(111)
        data = category_counts()
        if not data:
            ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="gray")
            ax.set_axis_off()
            return
        cats = [r[0] for r in data]
        counts = [r[1] for r in data]
        ax.barh(cats[::-1], counts[::-1], color="#1976d2")
        ax.set_title("Knowledge by category", fontsize=13, fontweight="bold")
        ax.set_xlabel("Topics")
        ax.tick_params(axis="y", labelsize=9)
        fig.tight_layout()

    def draw_conf(fig):
        fig.clear()
        ax = fig.add_subplot(111)
        data = confidence_bins()
        labels = [d[0] for d in data]
        vals = [d[1] for d in data]
        if not any(vals):
            ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="gray")
            ax.set_axis_off()
            return
        ax.bar(labels, vals, color="#388e3c")
        ax.set_title("Confidence distribution", fontsize=13,
                     fontweight="bold")
        ax.set_xlabel("Confidence bucket")
        ax.set_ylabel("Topics")
        ax.tick_params(axis="x", labelrotation=45, labelsize=9)
        fig.tight_layout()

    def draw_versions(fig):
        fig.clear()
        ax = fig.add_subplot(111)
        data = version_counts()
        if not data:
            ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                    transform=ax.transAxes, fontsize=14, color="gray")
            ax.set_axis_off()
            return
        labels = [f"v{r[0]}" for r in data]
        vals = [r[1] for r in data]
        ax.bar(labels, vals, color="#f57c00")
        ax.set_title("Knowledge version distribution", fontsize=13,
                     fontweight="bold")
        ax.set_xlabel("Version")
        ax.set_ylabel("Topics")
        fig.tight_layout()

    def draw_runs(fig):
        fig.clear()
        ax = fig.add_subplot(111)
        data = runs_per_cycle(40)
        if not data:
            ax.text(0.5, 0.5, "No learning runs yet", ha="center",
                    va="center", transform=ax.transAxes, fontsize=14,
                    color="gray")
            ax.set_axis_off()
            return
        cycles = [r[0] for r in data]
        added = [r[1] for r in data]
        refined = [r[2] for r in data]
        ax.plot(cycles, added, marker="o", color="#1976d2",
                label="items added")
        ax.plot(cycles, refined, marker="s", color="#d32f2f",
                label="items refined")
        ax.set_title("Learning activity over cycles", fontsize=13,
                     fontweight="bold")
        ax.set_xlabel("Cycle")
        ax.set_ylabel("Count")
        ax.legend()
        fig.tight_layout()

    def refresh_charts():
        try:
            draw_cat(c1.figure)
            c1.update()
            draw_conf(c2.figure)
            c2.update()
            draw_versions(c3.figure)
            c3.update()
            draw_runs(c4.figure)
            c4.update()
        except Exception as ex:
            print(f"chart refresh error: {ex}")

    refresh_charts()
    ui.timer(5.0, refresh_charts)


# =================================================================
# Dashboard
# =================================================================

@ui.page("/dashboard")
def dashboard_page():
    _header()
    _db_banner()
    ui.label("Learning Dashboard").classes("text-3xl font-bold mt-2")

    with ui.row().classes("gap-4 items-center mt-2 flex-wrap"):
        status_badge = ui.badge("idle", color="grey")
        cycles_label = ui.label("Cycles: 0")
        gemini_label = ui.label("Gemini calls: 0")
        kb_label = ui.label("Knowledge: 0")
        refined_label = ui.label("Refined: 0")
        error_label = ui.label("").classes("text-red-500")

    debug_label = ui.label("").classes("text-gray-600 mt-2")
    gemini_err_label = ui.label("").classes("text-orange-500 mt-1")

    async def do_start():
        await engine.start()
        refresh()

    async def do_pause():
        await engine.pause()
        refresh()

    async def do_one_cycle():
        ui.notify("Running one cycle…")
        try:
            await engine._cycle()
            engine.cycles_completed += 1
            ui.notify("Cycle complete.", color="green")
        except Exception as e:
            ui.notify(f"Cycle failed: {e}", color="red")
        refresh()

    with ui.row().classes("gap-2 mt-4"):
        ui.button("Start learning", on_click=do_start).props("color=green")
        ui.button("Pause", on_click=do_pause).props("color=orange")
        ui.button("Run one cycle now", on_click=do_one_cycle).props(
            "color=blue")

    def refresh():
        try:
            s = engine.stats()
        except Exception as e:
            s = {"cycles": 0, "gemini_calls": 0, "knowledge_total": 0,
                 "knowledge_refined": 0, "last_status": f"error: {e}",
                 "last_error": str(e), "last_debug": ""}
        status_badge.text = s["last_status"]
        status_badge.props(
            f'color={"green" if not engine.paused else "orange"}')
        cycles_label.text = f"Cycles: {s['cycles']}"
        gemini_label.text = f"Gemini calls: {s['gemini_calls']}"
        kb_label.text = f"Knowledge: {s['knowledge_total']}"
        refined_label.text = f"Refined: {s['knowledge_refined']}"
        error_label.text = s["last_error"][:200]
        debug_label.text = s["last_debug"]
        gemini_err_label.text = (
            f"Gemini: {gemini_mod.last_error}" if gemini_mod.last_error
            else "")

    ui.timer(2.0, refresh)
    refresh()

    ui.label("Recent learning runs").classes("text-2xl font-bold mt-6")
    runs_table = ui.table(
        columns=[
            {"name": "cycle", "label": "Cycle", "field": "cycle"},
            {"name": "topic", "label": "Topic", "field": "topic",
             "align": "left"},
            {"name": "added", "label": "Added", "field": "added"},
            {"name": "refined", "label": "Refined", "field": "refined"},
            {"name": "calls", "label": "Calls", "field": "calls"},
            {"name": "error", "label": "Error", "field": "error"},
            {"name": "created_at", "label": "When",
             "field": "created_at"},
        ],
        rows=[],
    ).classes("w-full mt-2")

    def refresh_runs():
        try:
            rows = recent_learning_runs(30)
        except Exception:
            rows = []
        runs_table.rows = [
            {
                "cycle": r[0], "topic": r[1], "added": r[2],
                "refined": r[3], "calls": r[4], "error": r[5],
                "created_at": (r[6] or "")[:19],
            }
            for r in rows
        ]

    ui.timer(5.0, refresh_runs)
    refresh_runs()

    ui.label("Recent document checks").classes("text-2xl font-bold mt-6")
    checks_table = ui.table(
        columns=[
            {"name": "filename", "label": "File", "field": "filename"},
            {"name": "type", "label": "Type", "field": "type"},
            {"name": "score", "label": "Score", "field": "score"},
            {"name": "summary", "label": "Summary", "field": "summary",
             "align": "left"},
            {"name": "created_at", "label": "When",
             "field": "created_at"},
        ],
        rows=[],
    ).classes("w-full mt-2")

    def refresh_checks():
        try:
            rows = recent_check_reports(30)
        except Exception:
            rows = []
        checks_table.rows = [
            {
                "filename": r[1], "type": r[2],
                "score": round(r[3] or 0, 2),
                "summary": (r[4] or "")[:120],
                "created_at": (r[5] or "")[:19],
            }
            for r in rows
        ]

    ui.timer(5.0, refresh_checks)
    refresh_checks()


ui.run(host="0.0.0.0", port=PORT, reload=False, title="HUBx v2")
