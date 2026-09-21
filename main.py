# main.py
# NiceGUI app with three tabs:
# 1. Check Document (upload + OCR + analysis + download reports)
# 2. Knowledge (browse the self-learned civil quality knowledge base)
# 3. Dashboard (learning loop stats)

import os
import asyncio
import tempfile

from nicegui import ui, app

from db import (init_db, get_all_knowledge, get_knowledge_by_id,
                save_check_report, recent_check_reports,
                recent_learning_runs, knowledge_stats)
from engine import engine
from file_reader import extract_text
from gemini import check_document
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


def _header():
    with ui.header().classes("items-center justify-between"):
        ui.label("HUBx v2 — Civil Quality Engineering").classes(
            "text-lg font-bold")
        with ui.row():
            ui.link("Check Document", "/").classes("text-white")
            ui.link("Knowledge", "/knowledge").classes("text-white")
            ui.link("Dashboard", "/dashboard").classes("text-white")


# =================================================================
# Tab 1 — Check Document
# =================================================================

@ui.page("/")
def check_page():
    _header()
    ui.label("Engineering Document Review").classes("text-2xl font-bold")
    ui.label(
        "Upload a PDF, TXT, XLSX, PNG or JPG. The AI checks it against "
        "Egyptian codes (ECP 203/205/202) and lists every mistake with a fix."
    ).classes("text-gray-600 mb-4")

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

    summary_box = ui.markdown("").classes("mt-2")
    score_label = ui.label("").classes("text-xl font-bold mt-2")

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
            ui.notify("Gemini returned no result.", color="red")
            return

        state["result"] = result
        score = float(result.get("score", 0.0))
        score_label.text = f"Score: {score:.2f} / 1.00"
        score_label.classes(
            replace="text-xl font-bold mt-2 " +
            ("text-green-600" if score >= 0.7 else "text-red-600"))
        summary_box.content = result.get("summary", "")
        issues_table.rows = result.get("issues", []) or []

        save_check_report(filename, ftype, text,
                          result.get("issues", []), score,
                          result.get("summary", ""))
        ui.notify(f"Found {len(result.get('issues', []))} issue(s).")

    ui.upload(on_upload=handle_upload,
              auto_upload=True,
              max_file_size=20_000_000,
              multiple=False).classes("w-full")

    ui.label("Result").classes("text-lg font-bold mt-6")
    score_label
    summary_box
    issues_table

    def dl_txt():
        if not state["result"]:
            ui.notify("Upload a file first.", color="orange"); return
        data = build_txt(state["filename"], state["result"])
        ui.download(data, filename="hubx_report.txt")

    def dl_pdf():
        if not state["result"]:
            ui.notify("Upload a file first.", color="orange"); return
        data = build_pdf(state["filename"], state["result"])
        ui.download(data, filename="hubx_report.pdf")

    def dl_xlsx():
        if not state["result"]:
            ui.notify("Upload a file first.", color="orange"); return
        data = build_xlsx(state["filename"], state["result"])
        ui.download(data, filename="hubx_report.xlsx")

    with ui.row().classes("gap-2 mt-4"):
        ui.button("Download TXT", on_click=dl_txt)
        ui.button("Download PDF", on_click=dl_pdf).props("color=red")
        ui.button("Download XLSX", on_click=dl_xlsx).props("color=green")


# =================================================================
# Tab 2 — Knowledge
# =================================================================

@ui.page("/knowledge")
def knowledge_page():
    _header()
    ui.label("Self-Learned Civil Quality Knowledge").classes(
        "text-2xl font-bold")

    stats = knowledge_stats()
    ui.label(
        f"Total topics: {stats['total']}  |  Refined: {stats['refined']}"
    ).classes("text-gray-600")

    categories = ["all"] + sorted({
        r[2] for r in get_all_knowledge(limit=1000) if r[2]
    })
    cat_select = ui.select(categories, value="all",
                           label="Category").classes("w-64 mt-2")

    table = ui.table(
        columns=[
            {"name": "topic", "label": "Topic", "field": "topic",
             "align": "left"},
            {"name": "category", "label": "Category", "field": "category"},
            {"name": "version", "label": "Ver", "field": "version"},
            {"name": "confidence", "label": "Conf",
             "field": "confidence"},
            {"name": "updated_at", "label": "Updated",
             "field": "updated_at"},
        ],
        rows=[],
        row_key="id",
    ).classes("w-full mt-4")

    detail_box = ui.markdown("").classes(
        "mt-4 p-4 border rounded w-full whitespace-pre-wrap")

    def load():
        cat = None if cat_select.value == "all" else cat_select.value
        rows = get_all_knowledge(category=cat, limit=500)
        table.rows = [
            {
                "id": r[0], "topic": r[1], "category": r[2],
                "version": r[5], "confidence": round(r[6] or 0, 2),
                "updated_at": (r[7] or "")[:19],
            }
            for r in rows
        ]

    def on_row_click(e):
        row = e.args[1] if isinstance(e.args, list) else e.args
        kid = row.get("id") if isinstance(row, dict) else None
        if not kid:
            return
        k = get_knowledge_by_id(kid)
        if not k:
            return
        body = k[4] or k[3] or "(empty)"
        detail_box.content = (
            f"### {k[1]}\n\n"
            f"*Category: {k[2]} — version {k[5]} — "
            f"confidence {round(k[6] or 0, 2)}*\n\n"
            f"{body}"
        )

    table.on("rowClick", on_row_click)
    cat_select.on("update:model-value", lambda _: load())
    load()

    ui.label("Click a row to read the full note.").classes(
        "text-gray-500 text-sm mt-2")


# =================================================================
# Tab 3 — Dashboard
# =================================================================

@ui.page("/dashboard")
def dashboard_page():
    _header()
    ui.label("Learning Dashboard").classes("text-2xl font-bold")

    with ui.row().classes("gap-4 items-center mt-2"):
        status_badge = ui.badge("idle", color="grey")
        cycles_label = ui.label("Cycles: 0")
        gemini_label = ui.label("Gemini calls: 0")
        kb_label = ui.label("Knowledge: 0")
        refined_label = ui.label("Refined: 0")
        error_label = ui.label("").classes("text-red-500")

    debug_label = ui.label("").classes("text-gray-600 mt-2")

    async def do_start():
        await engine.start()

    async def do_pause():
        await engine.pause()

    with ui.row().classes("gap-2 mt-4"):
        ui.button("Start learning", on_click=do_start).props("color=green")
        ui.button("Pause", on_click=do_pause).props("color=orange")

    def refresh():
        s = engine.stats()
        status_badge.text = s["last_status"]
        status_badge.props(
            f'color={"green" if not engine.paused else "orange"}')
        cycles_label.text = f"Cycles: {s['cycles']}"
        gemini_label.text = f"Gemini calls: {s['gemini_calls']}"
        kb_label.text = f"Knowledge: {s['knowledge_total']}"
        refined_label.text = f"Refined: {s['knowledge_refined']}"
        error_label.text = s["last_error"][:200]
        debug_label.text = s["last_debug"]

    ui.timer(2.0, refresh)

    ui.label("Recent learning runs").classes("text-lg font-bold mt-6")
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
        rows = recent_learning_runs(30)
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

    ui.label("Recent document checks").classes("text-lg font-bold mt-6")
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
        rows = recent_check_reports(30)
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
