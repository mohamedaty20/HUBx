# main.py
# NiceGUI app v3 - premium design, responsive, templates, AI search,
# per-topic downloads, analyze button.

import os
import asyncio
import tempfile
from collections import Counter

from nicegui import ui, app

from db import (init_db, get_all_knowledge, get_knowledge_by_id,
                search_knowledge, save_check_report, recent_check_reports,
                recent_learning_runs, knowledge_stats, db_health,
                category_counts, confidence_bins, version_counts,
                runs_per_cycle,
                get_all_templates, get_template_by_id,
                template_category_counts, template_stats,
                recent_template_runs)
from engine import engine
from file_reader import extract_text
from gemini import check_document, ai_search
import gemini as gemini_mod
from report_builder import (build_txt, build_pdf, build_xlsx,
                            topic_pdf, topic_txt, topic_docx)

PORT = int(os.getenv("PORT", "8080"))

init_db()

# ==================================================================
# Global CSS - JetBrains Mono + premium SaaS design + responsive
# ==================================================================

ui.add_head_html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {
    --hubx-bg: #0b1020;
    --hubx-surface: #131a2f;
    --hubx-surface-2: #1a2342;
    --hubx-border: #2a3559;
    --hubx-text: #e8ecf7;
    --hubx-text-dim: #9aa5c4;
    --hubx-primary: #4f8cff;
    --hubx-primary-2: #6aa8ff;
    --hubx-accent: #22d3a6;
    --hubx-warn: #f6a623;
    --hubx-danger: #ef4a5e;
    --hubx-radius: 12px;
    --hubx-radius-sm: 8px;
    --hubx-shadow: 0 6px 24px rgba(0,0,0,0.35);
}
* { font-family: 'JetBrains Mono', monospace !important; }
body, .q-page, .nicegui-content {
    background: var(--hubx-bg) !important;
    color: var(--hubx-text) !important;
    font-size: 14px;
}
.hubx-header {
    background: linear-gradient(90deg, #0d1428 0%, #1a2342 100%) !important;
    border-bottom: 1px solid var(--hubx-border);
    padding: 12px 24px;
    position: sticky; top: 0; z-index: 100;
}
.hubx-brand {
    font-weight: 800; font-size: 1.15rem;
    background: linear-gradient(90deg, #6aa8ff, #22d3a6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    letter-spacing: 0.5px;
}
.hubx-nav a {
    color: var(--hubx-text-dim) !important;
    text-decoration: none !important;
    padding: 8px 14px; border-radius: var(--hubx-radius-sm);
    font-weight: 500; font-size: 0.92rem;
    transition: all 0.15s ease;
}
.hubx-nav a:hover {
    color: var(--hubx-text) !important;
    background: rgba(79,140,255,0.12);
}
.hubx-card {
    background: var(--hubx-surface) !important;
    border: 1px solid var(--hubx-border);
    border-radius: var(--hubx-radius);
    box-shadow: var(--hubx-shadow);
    padding: 20px;
}
.hubx-card-flat {
    background: var(--hubx-surface) !important;
    border: 1px solid var(--hubx-border);
    border-radius: var(--hubx-radius);
    padding: 16px;
}
.hubx-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.3px;
              margin: 0 0 4px 0; }
.hubx-subtitle { color: var(--hubx-text-dim); font-size: 0.92rem;
                 margin-bottom: 16px; }
.hubx-btn {
    border-radius: var(--hubx-radius-sm) !important;
    font-weight: 600 !important;
    letter-spacing: 0.2px;
    text-transform: none !important;
    padding: 8px 18px !important;
}
.hubx-btn-primary { background: var(--hubx-primary) !important;
                    color: white !important; }
.hubx-btn-accent { background: var(--hubx-accent) !important;
                   color: #06210f !important; }
.hubx-btn-warn { background: var(--hubx-warn) !important;
                 color: #2a1a00 !important; }
.hubx-btn-danger { background: var(--hubx-danger) !important;
                   color: white !important; }
.hubx-btn-ghost { background: transparent !important;
                  border: 1px solid var(--hubx-border) !important;
                  color: var(--hubx-text) !important; }
.hubx-btn-ghost:hover { border-color: var(--hubx-primary) !important;
                        color: var(--hubx-primary) !important; }

/* Tight, readable knowledge body */
.hubx-body h1 { font-size: 1.55rem; font-weight: 800; margin: 0.2em 0 0.5em 0;
                line-height: 1.25; letter-spacing: -0.3px; }
.hubx-body h2 { font-size: 1.2rem; font-weight: 700; margin: 0.9em 0 0.35em 0;
                line-height: 1.3; color: var(--hubx-primary-2); }
.hubx-body h3 { font-size: 1.02rem; font-weight: 700; margin: 0.7em 0 0.25em 0;
                line-height: 1.3; }
.hubx-body p  { font-size: 0.9rem; line-height: 1.5; margin: 0.35em 0;
                color: var(--hubx-text); text-align: left !important; }
.hubx-body ul, .hubx-body ol { margin: 0.3em 0 0.5em 1.2em; }
.hubx-body li { font-size: 0.9rem; line-height: 1.45; margin: 0.15em 0;
                text-align: left !important; }
.hubx-body strong { font-weight: 700; color: #fff; }
.hubx-body table { width: 100%; border-collapse: collapse;
                   margin: 0.5em 0; font-size: 0.85rem; }
.hubx-body th, .hubx-body td {
    border: 1px solid var(--hubx-border); padding: 6px 8px;
    text-align: left !important;
}
.hubx-body th { background: var(--hubx-surface-2); font-weight: 700; }
.hubx-body code { background: var(--hubx-surface-2);
                  padding: 1px 6px; border-radius: 4px;
                  font-size: 0.85rem; }
.hubx-body hr { border: none; border-top: 1px solid var(--hubx-border);
                margin: 0.8em 0; }
.hubx-body blockquote {
    border-left: 3px solid var(--hubx-primary);
    padding-left: 12px; margin: 0.5em 0;
    color: var(--hubx-text-dim);
}

/* Sidebar buttons */
.hubx-side-btn {
    font-size: 0.88rem !important; font-weight: 500 !important;
    text-align: left !important; justify-content: flex-start !important;
    text-transform: none !important; padding: 8px 12px !important;
    border-radius: var(--hubx-radius-sm) !important;
    color: var(--hubx-text) !important; width: 100% !important;
    min-height: 36px !important;
}
.hubx-side-btn:hover { background: rgba(79,140,255,0.12) !important; }
.hubx-side-btn.selected {
    background: var(--hubx-primary) !important;
    color: white !important;
    font-weight: 700 !important;
}
.hubx-cat-header {
    font-size: 0.8rem; font-weight: 700; letter-spacing: 0.8px;
    color: var(--hubx-text-dim); text-transform: uppercase;
    margin: 10px 0 4px 4px;
}
.hubx-badge {
    padding: 2px 8px; border-radius: 10px; font-size: 0.72rem;
    font-weight: 700;
}
.hubx-badge-high { background: rgba(239,74,94,0.18); color: #ff8c9a; }
.hubx-badge-medium { background: rgba(246,166,35,0.18); color: #ffc270; }
.hubx-badge-low { background: rgba(34,211,166,0.18); color: #6ff0cb; }
.hubx-badge-v { background: rgba(79,140,255,0.18); color: #9ec2ff; }

/* Stat pill */
.hubx-stat {
    background: var(--hubx-surface-2); border: 1px solid var(--hubx-border);
    border-radius: var(--hubx-radius-sm); padding: 10px 14px;
    min-width: 110px;
}
.hubx-stat-label { font-size: 0.7rem; color: var(--hubx-text-dim);
                   letter-spacing: 0.6px; text-transform: uppercase; }
.hubx-stat-value { font-size: 1.2rem; font-weight: 800; color: #fff; }

/* Responsive */
@media (max-width: 768px) {
    .hubx-header { padding: 10px 12px; }
    .hubx-nav a { padding: 6px 8px; font-size: 0.8rem; }
    .hubx-title { font-size: 1.3rem; }
    .hubx-card { padding: 14px; }
    .hubx-body p, .hubx-body li { font-size: 0.85rem; }
    .hubx-stack-mobile { flex-direction: column !important; }
    .hubx-hide-mobile { display: none !important; }
}
</style>
""")


# ==================================================================
# Layout helpers
# ==================================================================

async def _keepalive():
    while True:
        await asyncio.sleep(600)
        try:
            import httpx
            base = os.getenv("RENDER_EXTERNAL_URL",
                             f"http://localhost:{PORT}")
            async with httpx.AsyncClient(timeout=10) as c:
                await c.get(base)
        except Exception:
            pass


app.on_startup(lambda: asyncio.create_task(_keepalive()))


def _header():
    with ui.row().classes("hubx-header items-center justify-between "
                          "w-full no-wrap"):
        ui.label("HUBx").classes("hubx-brand")
        with ui.row().classes("hubx-nav items-center gap-1"):
            ui.link("Check", "/")
            ui.link("Knowledge", "/knowledge")
            ui.link("Templates", "/templates")
            ui.link("Charts", "/charts")
            ui.link("Dashboard", "/dashboard")


def _db_banner():
    h = db_health()
    if h["mode"] == "local":
        with ui.row().classes("items-center gap-2 p-2 rounded w-full "
                              "mt-1").style(
                "background:rgba(246,166,35,0.12);"
                "border:1px solid rgba(246,166,35,0.35);"):
            ui.icon("warning").style("color:#f6a623")
            ui.label("Local SQLite - data lost on redeploy. Set "
                     "TURSO_DATABASE_URL on Render.").style(
                "color:#ffc270;font-size:0.85rem")
    elif h["mode"] == "turso":
        with ui.row().classes("items-center gap-2 p-2 rounded w-full "
                              "mt-1").style(
                "background:rgba(34,211,166,0.10);"
                "border:1px solid rgba(34,211,166,0.30);"):
            ui.icon("cloud_done").style("color:#22d3a6")
            ui.label(f"Connected to Turso - data persists").style(
                "color:#6ff0cb;font-size:0.85rem")


def _stat(label, value_id=None):
    with ui.column().classes("hubx-stat items-start gap-0"):
        ui.label(label).classes("hubx-stat-label")
        lbl = ui.label("0").classes("hubx-stat-value")
        return lbl


# ==================================================================
# Check Document page
# ==================================================================

@ui.page("/")
def check_page():
    _header()
    _db_banner()

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        ui.label("Engineering Document Review").classes("hubx-title")
        ui.label("Upload a PDF, TXT, XLSX, PNG or JPG. Press Analyze "
                 "to run the AI compliance check against Egyptian codes."
                 ).classes("hubx-subtitle")

        state = {"result": {}, "filename": "", "original_text": "",
                 "file_type": "", "extracted": False}

        # --- upload card ---
        with ui.card().classes("hubx-card w-full"):
            ui.label("1. Upload file").classes(
                "font-bold text-base mb-2")
            upload_status = ui.label("No file uploaded").classes(
                "text-sm").style("color:var(--hubx-text-dim)")

            async def handle_upload(e):
                data = await e.content.read()
                filename = e.name or "upload"
                ext = os.path.splitext(filename)[1].lower()
                tmp = tempfile.NamedTemporaryFile(delete=False,
                                                  suffix=ext)
                tmp.write(data)
                tmp.close()

                upload_status.text = f"Reading {filename}…"
                text, ftype = await extract_text(tmp.name, filename)
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

                if not text.strip():
                    upload_status.text = (
                        f"Could not extract text from {filename} "
                        f"(type={ftype})")
                    state["extracted"] = False
                    return

                state["filename"] = filename
                state["original_text"] = text
                state["file_type"] = ftype
                state["extracted"] = True
                upload_status.text = (
                    f"Ready: {filename}  ({len(text):,} characters "
                    f"extracted, type={ftype})")

            ui.upload(on_upload=handle_upload,
                      auto_upload=True,
                      max_file_size=20_000_000,
                      multiple=False).classes("w-full")

        # --- analyze card ---
        with ui.card().classes("hubx-card w-full"):
            ui.label("2. Analyze against Egyptian codes").classes(
                "font-bold text-base mb-2")
            err_label = ui.label("").style("color:#ef4a5e")
            analyze_btn = ui.button("Analyze now").classes(
                "hubx-btn hubx-btn-accent")
            progress = ui.linear_progress(value=0,
                                          show_value=False).classes(
                "w-full mt-2").style("opacity:0")

            async def do_analyze():
                if not state.get("extracted"):
                    ui.notify("Upload a file first.", color="orange")
                    return
                progress.style("opacity:1")
                err_label.text = ""
                ui.notify("Running compliance check…")
                result = await check_document(
                    state["filename"], state["file_type"],
                    state["original_text"])
                progress.style("opacity:0")
                if not result:
                    err_label.text = (
                        f"Gemini error: {gemini_mod.last_error}")
                    ui.notify("Analysis failed.", color="red")
                    return
                state["result"] = result
                render_result(state)
                try:
                    save_check_report(
                        state["filename"], state["file_type"],
                        state["original_text"],
                        result.get("issues", []),
                        float(result.get("score", 0.0)),
                        result.get("summary", ""))
                except Exception as ex:
                    ui.notify(f"Save failed: {ex}", color="orange")
                ui.notify(f"Found {len(result.get('issues', []))} "
                          f"issue(s).", color="green")

            analyze_btn.on("click", do_analyze)

        # --- result card ---
        result_card = ui.card().classes("hubx-card w-full")
        with result_card:
            ui.label("3. Result").classes("font-bold text-base mb-2")
            score_label = ui.label("").style(
                "font-size:1.4rem;font-weight:800")
            summary_box = ui.markdown("").classes("hubx-body mt-2")
            issues_table = ui.table(
                columns=[
                    {"name": "severity", "label": "Severity",
                     "field": "severity"},
                    {"name": "location", "label": "Location",
                     "field": "location"},
                    {"name": "problem", "label": "Problem",
                     "field": "problem", "align": "left"},
                    {"name": "fix", "label": "Fix", "field": "fix",
                     "align": "left"},
                    {"name": "reference", "label": "Reference",
                     "field": "reference"},
                ],
                rows=[],
            ).classes("w-full mt-3")

        def render_result(state):
            result = state["result"]
            score = float(result.get("score", 0.0))
            score_label.text = f"Score: {score:.2f} / 1.00"
            score_label.style(
                "color: #22d3a6" if score >= 0.7 else "color: #ef4a5e")
            summary_box.content = result.get("summary", "")
            issues_table.rows = result.get("issues", []) or []

        with ui.row().classes("gap-2 mt-3 flex-wrap"):
            ui.button("Download TXT", on_click=lambda: (
                ui.download(build_txt(state["filename"],
                                      state["result"]),
                            filename="hubx_report.txt")
                if state["result"] else
                ui.notify("Analyze first", color="orange"))
            ).classes("hubx-btn hubx-btn-ghost")
            ui.button("Download PDF", on_click=lambda: (
                ui.download(build_pdf(state["filename"],
                                      state["result"]),
                            filename="hubx_report.pdf")
                if state["result"] else
                ui.notify("Analyze first", color="orange"))
            ).classes("hubx-btn hubx-btn-danger")
            ui.button("Download XLSX", on_click=lambda: (
                ui.download(build_xlsx(state["filename"],
                                       state["result"]),
                            filename="hubx_report.xlsx")
                if state["result"] else
                ui.notify("Analyze first", color="orange"))
            ).classes("hubx-btn hubx-btn-primary")


# ==================================================================
# Knowledge page - with AI search
# ==================================================================

@ui.page("/knowledge")
def knowledge_page():
    _header()
    _db_banner()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-3"):
        ui.label("Knowledge Base").classes("hubx-title")
        ui.label("Self-learned civil quality notes. Search with AI, "
                 "browse by category, download any topic."
                 ).classes("hubx-subtitle")

        # --- search card ---
        with ui.card().classes("hubx-card w-full"):
            ui.label("AI Search").classes("font-bold text-base mb-2")
            with ui.row().classes("w-full gap-2 items-center no-wrap"):
                q_input = ui.input(
                    placeholder="e.g. What are the concrete curing "
                                "requirements in hot weather?"
                ).classes("flex-1")
                ask_btn = ui.button("Ask").classes(
                    "hubx-btn hubx-btn-primary")
            search_answer = ui.markdown("").classes("hubx-body mt-3")
            search_status = ui.label("").style(
                "color:var(--hubx-text-dim);font-size:0.85rem")

            async def do_search():
                q = (q_input.value or "").strip()
                if not q:
                    ui.notify("Type a question.", color="orange")
                    return
                search_status.text = "Searching knowledge base…"
                search_answer.content = ""
                # Pull matching excerpts
                rows = search_knowledge(q.split()[0], limit=8)
                if not rows:
                    rows = get_all_knowledge(limit=8)
                context_parts = []
                for r in rows:
                    body = (r[4] or r[3] or "")[:2000]
                    context_parts.append(f"### {r[1]}\n{body}")
                context = "\n\n".join(context_parts)[:14000]
                answer = await ai_search(q, context)
                if not answer:
                    search_status.text = (
                        f"AI error: {gemini_mod.last_error}")
                    return
                search_status.text = ""
                search_answer.content = answer

            ask_btn.on("click", do_search)
            q_input.on("keydown.enter", do_search)

        # --- browse card ---
        selected = {"cat": None}
        with ui.row().classes("w-full gap-3 no-wrap hubx-stack-mobile"):
            # Sidebar
            with ui.card().classes("hubx-card w-72 shrink-0 h-[75vh] "
                                   "overflow-auto"):
                ui.label("Categories").classes("font-bold text-base")
                cat_container = ui.column().classes("w-full gap-1 mt-2")
                ui.separator().style("border-color:var(--hubx-border)")
                ui.label("Topics").classes("font-bold text-base mt-2")
                topic_label = ui.label("").classes(
                    "text-xs").style("color:var(--hubx-text-dim)")
                topic_container = ui.column().classes("w-full gap-0.5")

            # Reader
            with ui.card().classes("hubx-card flex-1 h-[75vh] "
                                   "overflow-auto"):
                reader_toolbar = ui.row().classes(
                    "w-full gap-2 mb-2 items-center")
                detail = ui.markdown("").classes(
                    "hubx-body whitespace-pre-wrap w-full")

        def show_item(kid):
            k = get_knowledge_by_id(kid)
            if not k:
                return
            body = k[4] or k[3] or "(empty)"
            detail.content = (f"# {k[1]}\n\n"
                              f"**Category:** {k[2]}  ·  "
                              f"**Version:** v{k[5]}  ·  "
                              f"**Confidence:** {round(k[6] or 0, 2)}\n\n"
                              f"---\n\n{body}")
            reader_toolbar.clear()
            with reader_toolbar:
                ui.button("PDF", on_click=lambda: ui.download(
                    topic_pdf(k[1], k[2], k[5], body),
                    filename=f"hubx_{k[1][:30]}.pdf")
                ).classes("hubx-btn hubx-btn-danger")
                ui.button("DOCX", on_click=lambda: ui.download(
                    topic_docx(k[1], k[2], k[5], body),
                    filename=f"hubx_{k[1][:30]}.docx")
                ).classes("hubx-btn hubx-btn-primary")
                ui.button("TXT", on_click=lambda: ui.download(
                    topic_txt(k[1], k[2], k[5], body),
                    filename=f"hubx_{k[1][:30]}.txt")
                ).classes("hubx-btn hubx-btn-ghost")

        def render_topics():
            topic_container.clear()
            cat = selected["cat"]
            rows = get_all_knowledge(category=cat, limit=1000)
            topic_label.text = (f"{len(rows)} topics"
                                if cat else f"{len(rows)} topics total")
            with topic_container:
                if not rows:
                    ui.label("(empty)").classes(
                        "italic text-xs").style(
                        "color:var(--hubx-text-dim);padding:8px")
                for r in rows[:300]:
                    kid, topic, ver = r[0], r[1], r[5]
                    cls = "hubx-side-btn"
                    btn = ui.button(f"{topic[:48]}  ·  v{ver}"
                                    ).classes(cls)
                    btn.on("click", lambda k=kid: show_item(k))

        def render_categories():
            cat_container.clear()
            counts = category_counts()
            with cat_container:
                b = ui.button("All topics").classes(
                    "hubx-side-btn" +
                    (" selected" if selected["cat"] is None else ""))
                b.on("click", lambda: select_category(None))
                for cat, n in counts:
                    cls = "hubx-side-btn" + (
                        " selected" if selected["cat"] == cat else "")
                    b = ui.button(f"{cat}  ({n})").classes(cls)
                    b.on("click", lambda c=cat: select_category(c))

        def select_category(cat):
            selected["cat"] = cat
            render_categories()
            render_topics()

        def refresh_all():
            try:
                render_categories()
                render_topics()
            except Exception as e:
                print(f"refresh error: {e}")

        refresh_all()
        ui.timer(8.0, refresh_all)


# ==================================================================
# Templates page
# ==================================================================

@ui.page("/templates")
def templates_page():
    _header()
    _db_banner()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-3"):
        ui.label("Egyptian Site Paper Templates").classes("hubx-title")
        ui.label("Ready-to-use construction documents for Egyptian "
                 "companies. Generated and refined automatically. "
                 "Download any template as PDF."
                 ).classes("hubx-subtitle")

        tstats = template_stats()
        with ui.row().classes("gap-3 mb-2 flex-wrap"):
            _stat("Templates", str(tstats["total"]))
            _stat("Refined", str(tstats["refined"]))
            _stat("Queue", str(tstats["pending"]))

        selected = {"cat": None}
        with ui.row().classes("w-full gap-3 no-wrap hubx-stack-mobile"):
            with ui.card().classes("hubx-card w-72 shrink-0 h-[75vh] "
                                   "overflow-auto"):
                ui.label("Categories").classes("font-bold text-base")
                cat_container = ui.column().classes("w-full gap-1 mt-2")
                ui.separator().style("border-color:var(--hubx-border)")
                ui.label("Templates").classes("font-bold text-base mt-2")
                topic_label = ui.label("").classes(
                    "text-xs").style("color:var(--hubx-text-dim)")
                t_container = ui.column().classes("w-full gap-0.5")

            with ui.card().classes("hubx-card flex-1 h-[75vh] "
                                   "overflow-auto"):
                toolbar = ui.row().classes(
                    "w-full gap-2 mb-2 items-center")
                detail = ui.markdown("").classes(
                    "hubx-body whitespace-pre-wrap w-full")

        def show_template(tid):
            t = get_template_by_id(tid)
            if not t:
                return
            body = t[4] or t[3] or "(empty)"
            detail.content = (f"# {t[1]}\n\n"
                              f"**Category:** {t[2]}  ·  "
                              f"**Version:** v{t[5]}  ·  "
                              f"**Confidence:** {round(t[6] or 0, 2)}\n\n"
                              f"---\n\n{body}")
            toolbar.clear()
            with toolbar:
                ui.button("PDF", on_click=lambda: ui.download(
                    topic_pdf(t[1], t[2], t[5], body),
                    filename=f"hubx_tpl_{t[1][:30]}.pdf")
                ).classes("hubx-btn hubx-btn-danger")
                ui.button("DOCX", on_click=lambda: ui.download(
                    topic_docx(t[1], t[2], t[5], body),
                    filename=f"hubx_tpl_{t[1][:30]}.docx")
                ).classes("hubx-btn hubx-btn-primary")
                ui.button("TXT", on_click=lambda: ui.download(
                    topic_txt(t[1], t[2], t[5], body),
                    filename=f"hubx_tpl_{t[1][:30]}.txt")
                ).classes("hubx-btn hubx-btn-ghost")

        def render_templates():
            t_container.clear()
            cat = selected["cat"]
            rows = get_all_templates(category=cat, limit=500)
            topic_label.text = (f"{len(rows)} templates"
                                if cat else f"{len(rows)} total")
            with t_container:
                if not rows:
                    ui.label("(empty)").classes(
                        "italic text-xs").style(
                        "color:var(--hubx-text-dim);padding:8px")
                for r in rows[:300]:
                    tid, name, ver = r[0], r[1], r[5]
                    b = ui.button(f"{name[:44]}  ·  v{ver}").classes(
                        "hubx-side-btn")
                    b.on("click", lambda t=tid: show_template(t))

        def render_cats():
            cat_container.clear()
            counts = template_category_counts()
            with cat_container:
                b = ui.button("All categories").classes(
                    "hubx-side-btn" +
                    (" selected" if selected["cat"] is None else ""))
                b.on("click", lambda: sel(None))
                for cat, n in counts:
                    cls = "hubx-side-btn" + (
                        " selected" if selected["cat"] == cat else "")
                    b = ui.button(f"{cat}  ({n})").classes(cls)
                    b.on("click", lambda c=cat: sel(c))

        def sel(cat):
            selected["cat"] = cat
            render_cats()
            render_templates()

        def refresh():
            try:
                render_cats()
                render_templates()
            except Exception as e:
                print(f"tpl refresh: {e}")

        refresh()
        ui.timer(8.0, refresh)


# ==================================================================
# Charts page
# ==================================================================

@ui.page("/charts")
def charts_page():
    _header()
    _db_banner()
    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-3"):
        ui.label("Live Charts").classes("hubx-title")
        ui.label("Built from the self-learning loop. Auto-updates."
                 ).classes("hubx-subtitle")

        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        with ui.row().classes("w-full gap-3 flex-wrap"):
            c1 = ui.matplotlib(figsize=(6, 4)).classes(
                "hubx-card w-[48%] h-80")
            c2 = ui.matplotlib(figsize=(6, 4)).classes(
                "hubx-card w-[48%] h-80")
            c3 = ui.matplotlib(figsize=(10, 4)).classes(
                "hubx-card w-full h-80")
            c4 = ui.matplotlib(figsize=(10, 4)).classes(
                "hubx-card w-full h-80")

        def style_ax(ax, title):
            ax.set_facecolor("#0b1020")
            ax.figure.patch.set_facecolor("#131a2f")
            ax.title.set_color("#e8ecf7")
            ax.title.set_fontsize(12)
            ax.title.set_fontweight("bold")
            for s in ax.spines.values():
                s.set_color("#2a3559")
            ax.tick_params(colors="#9aa5c4", labelsize=9)
            ax.xaxis.label.set_color("#9aa5c4")
            ax.yaxis.label.set_color("#9aa5c4")

        def draw_cat(fig):
            fig.clear()
            ax = fig.add_subplot(111)
            data = category_counts()
            if not data:
                ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                        transform=ax.transAxes, color="#9aa5c4")
                ax.set_axis_off()
                return
            cats = [r[0] for r in data]
            counts = [r[1] for r in data]
            ax.barh(cats[::-1], counts[::-1], color="#4f8cff")
            ax.set_title("Knowledge by category")
            style_ax(ax, "Knowledge by category")
            fig.tight_layout()

        def draw_conf(fig):
            fig.clear()
            ax = fig.add_subplot(111)
            data = confidence_bins()
            labels = [d[0] for d in data]
            vals = [d[1] for d in data]
            if not any(vals):
                ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                        transform=ax.transAxes, color="#9aa5c4")
                ax.set_axis_off()
                return
            ax.bar(labels, vals, color="#22d3a6")
            ax.set_title("Confidence distribution")
            style_ax(ax, "Confidence distribution")
            ax.tick_params(axis="x", labelrotation=45)
            fig.tight_layout()

        def draw_versions(fig):
            fig.clear()
            ax = fig.add_subplot(111)
            data = version_counts()
            if not data:
                ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
                        transform=ax.transAxes, color="#9aa5c4")
                ax.set_axis_off()
                return
            labels = [f"v{r[0]}" for r in data]
            vals = [r[1] for r in data]
            ax.bar(labels, vals, color="#f6a623")
            ax.set_title("Version distribution")
            style_ax(ax, "Version distribution")
            fig.tight_layout()

        def draw_runs(fig):
            fig.clear()
            ax = fig.add_subplot(111)
            data = runs_per_cycle(40)
            if not data:
                ax.text(0.5, 0.5, "No runs yet", ha="center", va="center",
                        transform=ax.transAxes, color="#9aa5c4")
                ax.set_axis_off()
                return
            cycles = [r[0] for r in data]
            added = [r[1] for r in data]
            refined = [r[2] for r in data]
            ax.plot(cycles, added, marker="o", color="#4f8cff",
                    label="added")
            ax.plot(cycles, refined, marker="s", color="#ef4a5e",
                    label="refined")
            ax.set_title("Learning activity")
            style_ax(ax, "Learning activity")
            leg = ax.legend(facecolor="#131a2f", edgecolor="#2a3559")
            for t in leg.get_texts():
                t.set_color("#e8ecf7")
            fig.tight_layout()

        def refresh():
            try:
                draw_cat(c1.figure); c1.update()
                draw_conf(c2.figure); c2.update()
                draw_versions(c3.figure); c3.update()
                draw_runs(c4.figure); c4.update()
            except Exception as e:
                print(f"chart err: {e}")

        refresh()
        ui.timer(8.0, refresh)


# ==================================================================
# Dashboard
# ==================================================================

@ui.page("/dashboard")
def dashboard_page():
    _header()
    _db_banner()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-3"):
        ui.label("Learning Dashboard").classes("hubx-title")

        with ui.row().classes("gap-3 items-center flex-wrap"):
            status_badge = ui.badge("idle", color="grey").classes(
                "text-sm")
            cycles_label = _stat("Cycles")
            gemini_label = _stat("Gemini Calls")
            kb_label = _stat("Knowledge")
            refined_label = _stat("Refined")
            tpl_label = _stat("Templates")
            queue_label = _stat("Queue")

        debug_label = ui.label("").classes("text-sm").style(
            "color:var(--hubx-text-dim)")
        gemini_err_label = ui.label("").style(
            "color:#ffc270;font-size:0.85rem")

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

        with ui.row().classes("gap-2 mt-2"):
            ui.button("Start learning", on_click=do_start).classes(
                "hubx-btn hubx-btn-accent")
            ui.button("Pause", on_click=do_pause).classes(
                "hubx-btn hubx-btn-warn")
            ui.button("Run one cycle now", on_click=do_one_cycle
                      ).classes("hubx-btn hubx-btn-primary")

        def refresh():
            try:
                s = engine.stats()
            except Exception as e:
                s = {"cycles": 0, "gemini_calls": 0, "knowledge_total": 0,
                     "knowledge_refined": 0, "template_total": 0,
                     "pending_topics": 0, "last_status": f"error: {e}",
                     "last_error": str(e), "last_debug": ""}
            status_badge.text = s["last_status"]
            status_badge.props(
                f'color={"green" if not engine.paused else "orange"}')
            cycles_label.text = str(s["cycles"])
            gemini_label.text = str(s["gemini_calls"])
            kb_label.text = str(s["knowledge_total"])
            refined_label.text = str(s["knowledge_refined"])
            tpl_label.text = str(s.get("template_total", 0))
            queue_label.text = str(s.get("pending_topics", 0))
            debug_label.text = s["last_debug"]
            gemini_err_label.text = (
                f"Gemini: {gemini_mod.last_error}"
                if gemini_mod.last_error else "")

        ui.timer(2.0, refresh)
        refresh()

        ui.label("Recent learning runs").classes(
            "text-lg font-bold mt-4")
        runs_table = ui.table(columns=[
            {"name": "cycle", "label": "Cycle", "field": "cycle"},
            {"name": "topic", "label": "Topic", "field": "topic",
             "align": "left"},
            {"name": "added", "label": "+", "field": "added"},
            {"name": "refined", "label": "~", "field": "refined"},
            {"name": "calls", "label": "Calls", "field": "calls"},
            {"name": "error", "label": "Error", "field": "error"},
            {"name": "created_at", "label": "When",
             "field": "created_at"},
        ], rows=[]).classes("w-full")

        def refresh_runs():
            try:
                rows = recent_learning_runs(30)
            except Exception:
                rows = []
            runs_table.rows = [{
                "cycle": r[0], "topic": r[1], "added": r[2],
                "refined": r[3], "calls": r[4], "error": r[5],
                "created_at": (r[6] or "")[:19],
            } for r in rows]

        ui.timer(5.0, refresh_runs)
        refresh_runs()

        ui.label("Recent template runs").classes(
            "text-lg font-bold mt-4")
        tpl_table = ui.table(columns=[
            {"name": "cycle", "label": "Cycle", "field": "cycle"},
            {"name": "name", "label": "Template", "field": "name",
             "align": "left"},
            {"name": "added", "label": "+", "field": "added"},
            {"name": "refined", "label": "~", "field": "refined"},
            {"name": "error", "label": "Error", "field": "error"},
            {"name": "created_at", "label": "When",
             "field": "created_at"},
        ], rows=[]).classes("w-full")

        def refresh_tpl_runs():
            try:
                rows = recent_template_runs(20)
            except Exception:
                rows = []
            tpl_table.rows = [{
                "cycle": r[0], "name": r[1], "added": r[2],
                "refined": r[3], "error": r[5],
                "created_at": (r[6] or "")[:19],
            } for r in rows]

        ui.timer(5.0, refresh_tpl_runs)
        refresh_tpl_runs()


ui.run(host="0.0.0.0", port=PORT, reload=False, title="HUBx")
