# main.py
# NiceGUI app v4
# v5: mobile-first layout
# v6: slide-in drawer for categories/topics
# v7: reader flush-left, tables horizontally scrollable
# v8: engine auto-starts on boot; pause is persisted in DB.

import os
import io
import asyncio
import tempfile
import csv
from collections import Counter
from datetime import datetime

from nicegui import ui, app

from db import (init_db, get_all_knowledge, get_knowledge_by_id,
                search_knowledge, save_check_report, recent_check_reports,
                recent_learning_runs, knowledge_stats, db_health,
                category_counts, confidence_bins, version_counts,
                runs_per_cycle,
                get_all_templates, get_template_by_id,
                template_category_counts, template_stats,
                recent_template_runs,
                gemini_usage_stats,
                get_app_state, set_app_state)
from engine import engine, auto_start_if_needed
from file_reader import extract_text
from gemini import check_document, ai_search
import gemini as gemini_mod
from report_builder import (build_txt, build_pdf, build_xlsx,
                            topic_pdf, topic_txt, topic_docx)

PORT = int(os.getenv("PORT", "8080"))


class _State:
    focus = "both"
    lang  = "en"
    @property
    def run_knowledge(self): return self.focus in ("knowledge", "both")
    @property
    def run_templates(self): return self.focus in ("templates", "both")

STATE = _State()

STRINGS = {
    "en": {
        "brand": "HUBx",
        "nav_check": "Check",
        "nav_knowledge": "Knowledge",
        "nav_templates": "Templates",
        "nav_charts": "Charts",
        "nav_dashboard": "Dashboard",
        "focus_label": "AI Focus",
        "focus_knowledge": "Knowledge",
        "focus_templates": "Templates",
        "focus_both": "Both",
        "check_title": "Engineering Document Review",
        "check_sub": ("Upload a PDF, TXT, XLSX, PNG or JPG. Press Analyze "
                      "to run the AI compliance check against Egyptian codes."),
        "step1": "1. Upload file",
        "no_file": "No file uploaded",
        "step2": "2. Analyze against Egyptian codes",
        "analyze_now": "Analyze now",
        "step3": "3. Result",
        "dl_txt": "Download TXT",
        "dl_pdf": "Download PDF",
        "dl_xlsx": "Download XLSX",
        "knowledge_title": "Knowledge Base",
        "knowledge_sub": ("Self-learned civil quality notes. Search with AI, "
                          "browse by category, download any topic."),
        "ai_search": "AI Search",
        "ask": "Ask",
        "ask_ph": "e.g. What are the concrete curing requirements in hot weather?",
        "categories": "Categories",
        "topics": "Topics",
        "all_topics": "All topics",
        "browse": "Browse",
        "templates_title": "Egyptian Site Paper Templates",
        "templates_sub": ("Ready-to-use construction documents for Egyptian "
                          "companies. Generated and refined automatically. "
                          "Download as PDF, DOCX or TXT."),
        "templates_word": "Templates",
        "refined_word": "Refined",
        "queue_word": "Queue",
        "all_categories": "All categories",
        "preview_paper": "Paper view",
        "btn_pdf": "PDF",
        "btn_docx": "DOCX",
        "btn_txt": "TXT",
        "charts_title": "Live Charts",
        "charts_sub": "Built from the self-learning loop. Auto-updates.",
        "dash_title": "Learning Dashboard",
        "start": "Start learning",
        "pause": "Pause",
        "one_cycle": "Run one cycle now",
        "cycles": "Cycles",
        "gemini_calls": "Gemini Calls",
        "knowledge_stat": "Knowledge",
        "refined_stat": "Refined",
        "templates_stat": "Templates",
        "queue_stat": "Queue",
        "recent_runs": "Recent learning runs",
        "recent_tpl_runs": "Recent template runs",
        "paper_preview": "Paper preview",
        "close": "Close",
        "download_pdf": "Download PDF",
        "project_name": "Project Name",
        "engineer": "Engineer",
        "supervisor": "Supervisor",
        "company": "Company",
        "location": "Location",
        "date": "Date",
        "category": "Category",
        "version": "Version",
        "confidence": "Confidence",
        "description": "Description",
        "no_selection": "Tap ☰ to pick a topic.",
    },
    "ar": {
        "brand": "HUBx",
        "nav_check": "الفحص",
        "nav_knowledge": "المعرفة",
        "nav_templates": "القوالب",
        "nav_charts": "الرسوم",
        "nav_dashboard": "لوحة التحكم",
        "focus_label": "تركيز الذكاء",
        "focus_knowledge": "المعرفة",
        "focus_templates": "القوالب",
        "focus_both": "الاثنان",
        "check_title": "مراجعة المستندات الهندسية",
        "check_sub": ("ارفع ملف PDF أو TXT أو XLSX أو صورة. اضغط تحليل "
                      "لتشغيل الفحص الآلي مقابل الكود المصري."),
        "step1": "١. رفع الملف",
        "no_file": "لم يتم رفع ملف",
        "step2": "٢. التحليل حسب الكود المصري",
        "analyze_now": "تحليل الآن",
        "step3": "٣. النتيجة",
        "dl_txt": "تحميل TXT",
        "dl_pdf": "تحميل PDF",
        "dl_xlsx": "تحميل XLSX",
        "knowledge_title": "قاعدة المعرفة",
        "knowledge_sub": ("ملاحظات الجودة المدنية المُتعلَّمة ذاتياً. ابحث "
                          "بالذكاء الاصطناعي، تصفح حسب الفئة، حمّل أي موضوع."),
        "ai_search": "بحث بالذكاء الاصطناعي",
        "ask": "اسأل",
        "ask_ph": "مثال: ما متطلبات معالجة الخرسانة في الجو الحار؟",
        "categories": "الفئات",
        "topics": "المواضيع",
        "all_topics": "كل المواضيع",
        "browse": "تصفح",
        "templates_title": "قوالب الأوراق للمواقع المصرية",
        "templates_sub": ("مستندات جاهزة للشركات المصرية. تُولَّد وتُحسَّن "
                          "تلقائياً. حمّلها PDF أو DOCX أو TXT."),
        "templates_word": "القوالب",
        "refined_word": "مُحسَّن",
        "queue_word": "بالانتظار",
        "all_categories": "كل الفئات",
        "preview_paper": "عرض الورقة",
        "btn_pdf": "PDF",
        "btn_docx": "DOCX",
        "btn_txt": "TXT",
        "charts_title": "الرسوم الحية",
        "charts_sub": "مبنية من حلقة التعلم الذاتي. تتحدث تلقائياً.",
        "dash_title": "لوحة التعلم",
        "start": "ابدأ التعلم",
        "pause": "إيقاف",
        "one_cycle": "دورة واحدة الآن",
        "cycles": "الدورات",
        "gemini_calls": "استدعاءات Gemini",
        "knowledge_stat": "المعرفة",
        "refined_stat": "مُحسَّن",
        "templates_stat": "القوالب",
        "queue_stat": "بالانتظار",
        "recent_runs": "آخر دورات التعلم",
        "recent_tpl_runs": "آخر دورات القوالب",
        "paper_preview": "معاينة الورقة",
        "close": "إغلاق",
        "download_pdf": "تحميل PDF",
        "project_name": "اسم المشروع",
        "engineer": "المهندس",
        "supervisor": "المشرف",
        "company": "الشركة",
        "location": "الموقع",
        "date": "التاريخ",
        "category": "الفئة",
        "version": "الإصدار",
        "confidence": "الثقة",
        "description": "الوصف",
        "no_selection": "اضغط ☰ لاختيار موضوع.",
    },
}

def t(key: str) -> str:
    return STRINGS.get(STATE.lang, STRINGS["en"]).get(key, key)

def is_rtl() -> bool:
    return STATE.lang == "ar"

init_db()

# ============================================================
# CSS
# ============================================================
ui.add_head_html("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
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
* { font-family: 'JetBrains Mono', 'Cairo', monospace !important; }
body.lang-ar, body.lang-ar * { font-family: 'Cairo', 'JetBrains Mono', sans-serif !important; }
body.lang-ar { direction: rtl; }
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
.hubx-lang-btn {
    min-width: 40px !important; min-height: 32px !important;
    padding: 4px 10px !important; font-weight: 700 !important;
    font-size: 0.82rem !important;
}
.hubx-lang-btn.active {
    background: var(--hubx-primary) !important;
    color: white !important;
}
.hubx-card {
    background: var(--hubx-surface) !important;
    border: 1px solid var(--hubx-border) !important;
    border-radius: var(--hubx-radius) !important;
    box-shadow: var(--hubx-shadow);
    padding: 20px;
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

.hubx-body h1 { font-size: 1.55rem; font-weight: 800; margin: 0.2em 0 0.5em 0;
                line-height: 1.25; letter-spacing: -0.3px; }
.hubx-body h2 { font-size: 1.2rem; font-weight: 700; margin: 0.9em 0 0.35em 0;
                line-height: 1.3; color: var(--hubx-primary-2); }
.hubx-body h3 { font-size: 1.02rem; font-weight: 700; margin: 0.7em 0 0.25em 0;
                line-height: 1.3; }
.hubx-body p  { font-size: 0.95rem; line-height: 1.6; margin: 0.4em 0;
                color: var(--hubx-text); text-align: left !important; }
.hubx-body ul, .hubx-body ol {
    margin: 0.3em 0 0.6em 0;
    padding-left: 0;
    list-style-position: inside;
}
.hubx-body li { font-size: 0.95rem; line-height: 1.55; margin: 0.15em 0;
                text-align: left !important; padding-left: 0; }
.hubx-body strong { font-weight: 700; color: #fff; }

.hubx-body table {
    display: block;
    overflow-x: auto;
    max-width: 100%;
    width: 100%;
    border-collapse: collapse;
    margin: 0.5em 0;
    font-size: 0.85rem;
    -webkit-overflow-scrolling: touch;
}
.hubx-body th, .hubx-body td {
    border: 1px solid var(--hubx-border);
    padding: 6px 8px;
    text-align: left !important;
    white-space: normal;
    word-break: break-word;
    min-width: 90px;
    vertical-align: top;
}
.hubx-body th { background: var(--hubx-surface-2); font-weight: 700; }
.hubx-body code { background: var(--hubx-surface-2);
                  padding: 1px 6px; border-radius: 4px;
                  font-size: 0.88rem; }
.hubx-body hr { border: none; border-top: 1px solid var(--hubx-border);
                margin: 0.8em 0; }
.hubx-body blockquote {
    border-left: 3px solid var(--hubx-primary);
    padding-left: 12px; margin: 0.5em 0;
    color: var(--hubx-text-dim);
}
body.lang-ar .hubx-body p, body.lang-ar .hubx-body li,
body.lang-ar .hubx-body h1, body.lang-ar .hubx-body h2,
body.lang-ar .hubx-body h3 {
    text-align: right !important;
}
body.lang-ar .hubx-body blockquote {
    border-left: none; border-right: 3px solid var(--hubx-primary);
    padding-left: 0; padding-right: 12px;
}
body.lang-ar .hubx-body ul, body.lang-ar .hubx-body ol {
    padding-left: 0; padding-right: 0;
    list-style-position: inside;
}

.hubx-drawer-btn {
    font-size: 0.84rem !important; font-weight: 500 !important;
    text-align: left !important; justify-content: flex-start !important;
    text-transform: none !important; padding: 6px 10px !important;
    border-radius: 6px !important;
    color: var(--hubx-text) !important; width: 100% !important;
    min-height: 34px !important;
    line-height: 1.25 !important;
    white-space: normal !important;
}
body.lang-ar .hubx-drawer-btn {
    text-align: right !important; justify-content: flex-end !important;
}
.hubx-drawer-btn:hover { background: rgba(79,140,255,0.12) !important; }
.hubx-drawer-btn.selected {
    background: var(--hubx-primary) !important;
    color: white !important;
    font-weight: 700 !important;
}

.hubx-badge {
    padding: 2px 8px; border-radius: 10px; font-size: 0.72rem;
    font-weight: 700;
}
.hubx-stat {
    background: var(--hubx-surface-2); border: 1px solid var(--hubx-border);
    border-radius: var(--hubx-radius-sm); padding: 10px 14px;
    min-width: 110px;
}
.hubx-stat-label { font-size: 0.7rem; color: var(--hubx-text-dim);
                   letter-spacing: 0.6px; text-transform: uppercase; }
.hubx-stat-value { font-size: 1.2rem; font-weight: 800; color: #fff; }

.hubx-drawer { background: var(--hubx-surface) !important; }
.hubx-drawer .q-drawer__content { background: var(--hubx-surface) !important; }

.hubx-paper {
    background: #ffffff; color: #111111;
    width: 210mm; min-height: 297mm;
    padding: 20mm 18mm 22mm 18mm;
    box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    font-family: 'Cairo', 'JetBrains Mono', sans-serif !important;
    font-size: 12pt; line-height: 1.55;
    direction: ltr;
}
.hubx-paper.rtl { direction: rtl; text-align: right; }
.hubx-paper * { font-family: 'Cairo', 'JetBrains Mono', sans-serif !important; }
.hubx-paper .cover { text-align: center; padding-top: 30mm; }
.hubx-paper .cover .org { font-size: 14pt; font-weight: 700;
                          letter-spacing: .5px; }
.hubx-paper .cover .faculty { font-size: 12pt; margin-top: 4mm; color: #333; }
.hubx-paper .cover .rule { height: 2px; background: #111;
                           margin: 8mm auto; width: 60%; }
.hubx-paper .cover .ptitle { font-size: 22pt; font-weight: 800;
                             margin: 10mm 0; }
.hubx-paper .cover .subtitle { font-size: 13pt; color: #444;
                               margin-bottom: 12mm; }
.hubx-paper .meta { width: 100%; margin-top: 18mm; border-collapse: collapse; }
.hubx-paper .meta td { padding: 3mm 2mm; font-size: 12pt; vertical-align: top; }
.hubx-paper .meta .lbl { width: 35%; font-weight: 700; color: #222; }
.hubx-paper .meta .val { width: 65%; border-bottom: 1px dotted #999; }
.hubx-paper .section { margin-top: 10mm; }
.hubx-paper .section h2 { font-size: 14pt; border-bottom: 1.5px solid #111;
                          padding-bottom: 2mm; margin-bottom: 4mm; color: #111; }
.hubx-paper .section .body { text-align: justify; }
.hubx-paper .body p, .hubx-paper .body li {
    font-size: 12pt !important; color: #111 !important;
    line-height: 1.55 !important;
}
.hubx-paper .body h1, .hubx-paper .body h2, .hubx-paper .body h3 {
    color: #111 !important;
}
.hubx-paper .body table { border-collapse: collapse; width: 100%; }
.hubx-paper .body th, .hubx-paper .body td {
    border: 1px solid #333; padding: 4px 6px; color: #111;
}
.hubx-paper .footer { margin-top: 14mm; text-align: center;
                      font-size: 9pt; color: #666;
                      border-top: 1px solid #ccc; padding-top: 4mm; }

@media (max-width: 768px) {
    html, body { overflow-x: hidden !important; max-width: 100vw !important; }
    .q-page, .nicegui-content { overflow-x: hidden !important; }

    .hubx-header {
        padding: 8px 10px !important;
        flex-wrap: wrap !important;
        gap: 6px !important;
    }
    .hubx-header > .row {
        flex-wrap: wrap !important;
        gap: 6px !important;
        width: 100% !important;
    }
    .hubx-brand { font-size: 1rem !important; }
    .hubx-nav {
        width: 100% !important;
        flex-wrap: wrap !important;
        gap: 2px !important;
        justify-content: space-between !important;
    }
    .hubx-nav a {
        padding: 6px 4px !important;
        font-size: 0.72rem !important;
        flex: 1 1 auto !important;
        text-align: center !important;
    }
    .hubx-lang-btn {
        min-width: 32px !important;
        min-height: 28px !important;
        padding: 2px 6px !important;
        font-size: 0.72rem !important;
    }

    .hubx-title { font-size: 1.15rem !important; }
    .hubx-subtitle { font-size: 0.8rem !important;
                     margin-bottom: 10px !important; }
    .hubx-card { padding: 12px !important; }

    .hubx-body p, .hubx-body li { font-size: 0.92rem !important; }
    .hubx-body h1 { font-size: 1.25rem !important; }
    .hubx-body h2 { font-size: 1.05rem !important; }
    .hubx-body h3 { font-size: 0.98rem !important; }
    .hubx-body table { font-size: 0.8rem !important; }
    .hubx-body th, .hubx-body td { min-width: 80px !important;
                                   padding: 5px 6px !important; }

    .hubx-stat { min-width: 80px !important; padding: 8px 10px !important; }
    .hubx-stat-value { font-size: 1rem !important; }
    .hubx-stat-label { font-size: 0.62rem !important; }

    .hubx-paper { width: 100% !important; padding: 10px !important;
                  min-height: auto !important; }

    .q-table__container { overflow-x: auto !important; }
    .q-table { font-size: 0.75rem !important; }
    .q-table th, .q-table td { padding: 4px 6px !important; }

    .q-dialog__inner > div { max-width: 96vw !important; }

    .hubx-drawer { width: 84vw !important; max-width: 84vw !important; }
}
</style>
""", shared=True)

# ---- paper PDF serving ----
import uuid
from fastapi import Response as _FastResponse

_PAPER_CACHE: dict[str, bytes] = {}
_PAPER_ORDER: list[str] = []

def _cache_paper_pdf(pdf_bytes: bytes) -> str:
    tok = uuid.uuid4().hex
    _PAPER_CACHE[tok] = pdf_bytes
    _PAPER_ORDER.append(tok)
    while len(_PAPER_ORDER) > 50:
        old = _PAPER_ORDER.pop(0)
        _PAPER_CACHE.pop(old, None)
    return tok

@app.get("/paper/{token}")
def _serve_paper(token: str):
    pdf = _PAPER_CACHE.get(token)
    if not pdf:
        return _FastResponse(status_code=404, content="not found")
    return _FastResponse(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{token}.pdf"'},
    )


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


def _boot_tasks():
    asyncio.create_task(_keepalive())
    asyncio.create_task(auto_start_if_needed())


app.on_startup(_boot_tasks)


def _apply_body_class():
    cls = "lang-ar" if is_rtl() else "lang-en"
    ui.run_javascript(
        f"document.body.classList.remove('lang-ar','lang-en');"
        f"document.body.classList.add('{cls}');"
    )

def set_lang(code: str):
    STATE.lang = code
    app.storage.user["lang"] = code
    ui.navigate.reload()

def set_focus(mode: str):
    STATE.focus = mode
    app.storage.user["focus"] = mode
    ui.notify(f"{t('focus_label')}: {mode}", color="primary")

def _lang_toggle():
    with ui.row().classes("gap-1 items-center"):
        cls_en = "hubx-lang-btn" + (" active" if STATE.lang == "en" else "")
        cls_ar = "hubx-lang-btn" + (" active" if STATE.lang == "ar" else "")
        ui.button("EN", on_click=lambda: set_lang("en")).classes(cls_en)
        ui.button("ع",  on_click=lambda: set_lang("ar")).classes(cls_ar)

def _focus_selector():
    with ui.row().classes("gap-2 items-center"):
        ui.label(t("focus_label")).style(
            "color:var(--hubx-text-dim);font-size:0.82rem")
        ui.toggle(
            {"knowledge": t("focus_knowledge"),
             "templates": t("focus_templates"),
             "both":      t("focus_both")},
            value=STATE.focus,
            on_change=lambda e: set_focus(e.value),
        ).props("dense")


def _header():
    with ui.row().classes("hubx-header items-center justify-between "
                          "w-full flex-wrap gap-2"):
        with ui.row().classes("items-center gap-3 flex-wrap"):
            ui.label(t("brand")).classes("hubx-brand")
            _focus_selector()
        with ui.row().classes("hubx-nav items-center gap-1 flex-wrap"):
            ui.link(t("nav_check"), "/")
            ui.link(t("nav_knowledge"), "/knowledge")
            ui.link(t("nav_templates"), "/templates")
            ui.link(t("nav_charts"), "/charts")
            ui.link(t("nav_dashboard"), "/dashboard")
        _lang_toggle()


def _db_banner():
    h = db_health()
    if h["mode"] == "local":
        with ui.row().classes("items-center gap-2 p-2 rounded w-full "
                              "mt-1 flex-wrap").style(
                "background:rgba(246,166,35,0.12);"
                "border:1px solid rgba(246,166,35,0.35);"):
            ui.label("⚠").style("color:#f6a623;font-weight:700;"
                                "font-size:1.1rem;flex-shrink:0")
            ui.label("Local SQLite - data lost on redeploy. Set "
                     "TURSO_DATABASE_URL on Render.").style(
                "color:#ffc270;font-size:0.85rem")
    elif h["mode"] == "turso":
        with ui.row().classes("items-center gap-2 p-2 rounded w-full "
                              "mt-1 flex-wrap").style(
                "background:rgba(34,211,166,0.10);"
                "border:1px solid rgba(34,211,166,0.30);"):
            ui.label("✓").style("color:#22d3a6;font-weight:700;"
                                "font-size:1.1rem;flex-shrink:0")
            ui.label("Connected to Turso - data persists").style(
                "color:#6ff0cb;font-size:0.85rem")


def _stat(label):
    with ui.column().classes("hubx-stat items-start gap-0"):
        ui.label(label).classes("hubx-stat-label")
        lbl = ui.label("0").classes("hubx-stat-value")
        return lbl


def _paper_html(title: str, category: str, version, body_md: str,
                meta: dict | None = None) -> str:
    meta = meta or {}
    rtl = is_rtl()
    rtl_cls = " rtl" if rtl else ""
    today = datetime.utcnow().date().isoformat()
    body_html = _md_to_html(body_md or "")

    fields = [
        (t("project_name"), meta.get("project_name") or title),
        (t("engineer"),     meta.get("engineer") or ""),
        (t("supervisor"),   meta.get("supervisor") or ""),
        (t("company"),      meta.get("company") or ""),
        (t("location"),     meta.get("location") or ""),
        (t("category"),     category or ""),
        (t("version"),      f"v{version}" if version is not None else ""),
        (t("date"),         meta.get("date") or today),
    ]
    rows = "".join(
        f'<tr><td class="lbl">{k}</td><td class="val">{v or "&nbsp;"}</td></tr>'
        for k, v in fields
    )

    return f"""<!doctype html>
<html lang="{'ar' if rtl else 'en'}" dir="{'rtl' if rtl else 'ltr'}">
<head><meta charset="utf-8"></head>
<body>
<div class="hubx-paper{rtl_cls}">
  <div class="cover">
    <div class="org">{meta.get('company') or 'Egyptian Engineering Co.'}</div>
    <div class="faculty">{meta.get('location') or 'Egypt'}</div>
    <div class="rule"></div>
    <div class="ptitle">{title or ''}</div>
    <div class="subtitle">{category or 'Civil Engineering Document'}</div>
  </div>

  <table class="meta">{rows}</table>

  <div class="section">
    <h2>{t('description')}</h2>
    <div class="body">{body_html}</div>
  </div>

  <div class="footer">HUBx · {today}</div>
</div>
</body></html>"""


def _md_to_html(md: str) -> str:
    import html as _html
    import re
    lines = md.replace("\r\n", "\n").split("\n")
    out = []
    in_ul = in_ol = False
    in_table = False
    table_buf = []

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul: out.append("</ul>"); in_ul = False
        if in_ol: out.append("</ol>"); in_ol = False

    def flush_table():
        nonlocal in_table, table_buf
        if not table_buf:
            in_table = False
            return
        rows = [r for r in table_buf if r.strip()]
        table_buf = []
        if len(rows) >= 1:
            out.append("<table>")
            for i, r in enumerate(rows):
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                tag = "th" if i == 0 else "td"
                out.append("<tr>" + "".join(
                    f"<{tag}>{_inline(c)}</{tag}>" for c in cells) + "</tr>")
            out.append("</table>")
        in_table = False

    def _inline(s: str) -> str:
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        return s

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("|") and line.endswith("|"):
            in_table = True
            table_buf.append(line)
            continue
        if in_table:
            flush_table()

        if not line.strip():
            close_lists()
            continue
        if line.startswith("### "):
            close_lists(); out.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            close_lists(); out.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            close_lists(); out.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.strip() in ("---", "***", "___"):
            close_lists(); out.append("<hr>")
        elif line.lstrip().startswith(("- ", "* ")):
            if in_ol: out.append("</ol>"); in_ol = False
            if not in_ul: out.append("<ul>"); in_ul = True
            out.append(f"<li>{_inline(line.lstrip()[2:])}</li>")
        elif re.match(r"^\s*\d+\.\s", line):
            if in_ul: out.append("</ul>"); in_ul = False
            if not in_ol: out.append("<ol>"); in_ol = True
            out.append(f"<li>{_inline(re.sub(r'^\s*\d+\.\s', '', line))}</li>")
        else:
            close_lists()
            out.append(f"<p>{_inline(line)}</p>")

    close_lists()
    if in_table: flush_table()
    return "\n".join(out)


def _paper_pdf_bytes(html_str: str, rtl: bool) -> bytes:
    full = f"""<!doctype html><html><head><meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
      @page {{ size: A4; margin: 0; }}
      body {{ margin:0; background:#fff; color:#111;
             font-family:'Cairo','JetBrains Mono',sans-serif; }}
      .hubx-paper {{ width:210mm; min-height:297mm; padding:20mm 18mm 22mm 18mm;
                     box-sizing:border-box; }}
      .hubx-paper.rtl {{ direction: rtl; text-align:right; }}
      .hubx-paper .cover {{ text-align:center; padding-top:30mm; }}
      .hubx-paper .cover .org {{ font-size:14pt; font-weight:700; }}
      .hubx-paper .cover .faculty {{ font-size:12pt; margin-top:4mm; color:#333; }}
      .hubx-paper .cover .rule {{ height:2px; background:#111;
                                  margin:8mm auto; width:60%; }}
      .hubx-paper .cover .ptitle {{ font-size:22pt; font-weight:800;
                                    margin:10mm 0; }}
      .hubx-paper .cover .subtitle {{ font-size:13pt; color:#444;
                                      margin-bottom:12mm; }}
      .hubx-paper .meta {{ width:100%; margin-top:18mm; border-collapse:collapse; }}
      .hubx-paper .meta td {{ padding:3mm 2mm; font-size:12pt; vertical-align:top; }}
      .hubx-paper .meta .lbl {{ width:35%; font-weight:700; color:#222; }}
      .hubx-paper .meta .val {{ width:65%; border-bottom:1px dotted #999; }}
      .hubx-paper .section {{ margin-top:10mm; }}
      .hubx-paper .section h2 {{ font-size:14pt; border-bottom:1.5px solid #111;
                                 padding-bottom:2mm; margin-bottom:4mm; color:#111; }}
      .hubx-paper .body {{ text-align:justify; }}
      .hubx-paper .body table {{ border-collapse:collapse; width:100%; }}
      .hubx-paper .body th, .hubx-paper .body td {{
          border:1px solid #333; padding:4px 6px; color:#111; }}
      .hubx-paper .footer {{ margin-top:14mm; text-align:center; font-size:9pt;
                             color:#666; border-top:1px solid #ccc;
                             padding-top:4mm; }}
    </style></head><body>{html_str}</body></html>"""
    try:
        from weasyprint import HTML
        return HTML(string=full).write_pdf()
    except Exception as e:
        print(f"[paper_pdf] WeasyPrint failed: {e}")
        raise


def _paper_body_html(title: str, category: str, version,
                     body_md: str, meta: dict | None = None) -> str:
    meta = meta or {}
    rtl = is_rtl()
    rtl_cls = " rtl" if rtl else ""
    today = datetime.utcnow().date().isoformat()
    body_html = _md_to_html(body_md or "")

    fields = [
        (t("project_name"), meta.get("project_name") or title),
        (t("engineer"),     meta.get("engineer") or ""),
        (t("supervisor"),   meta.get("supervisor") or ""),
        (t("company"),      meta.get("company") or ""),
        (t("location"),     meta.get("location") or ""),
        (t("category"),     category or ""),
        (t("version"),      f"v{version}" if version is not None else ""),
        (t("date"),         meta.get("date") or today),
    ]
    rows = "".join(
        f'<tr><td class="lbl">{k}</td>'
        f'<td class="val">{v or "&nbsp;"}</td></tr>'
        for k, v in fields
    )

    return f"""<div class="hubx-paper{rtl_cls}">
  <div class="cover">
    <div class="org">{meta.get('company') or 'Egyptian Engineering Co.'}</div>
    <div class="faculty">{meta.get('location') or 'Egypt'}</div>
    <div class="rule"></div>
    <div class="ptitle">{title or ''}</div>
    <div class="subtitle">{category or 'Civil Engineering Document'}</div>
  </div>
  <table class="meta">{rows}</table>
  <div class="section">
    <h2>{t('description')}</h2>
    <div class="body">{body_html}</div>
  </div>
  <div class="footer">HUBx · {today}</div>
</div>"""


def _open_paper_dialog(title: str, category: str, version,
                       body_md: str, meta: dict | None = None):
    body_div  = _paper_body_html(title, category, version, body_md, meta)
    full_html = _paper_html(title, category, version, body_md, meta)

    with ui.dialog() as d:
        with ui.card().classes("hubx-card").style(
                "max-width:96vw; max-height:96vh; "
                "overflow:auto; width:auto; padding:16px;"):
            ui.label(t("paper_preview")).classes("text-lg font-bold mb-2")

            with ui.element("div").style(
                    "background:#e9edf5; padding:16px; "
                    "border-radius:10px; overflow:auto;"):
                ui.html(body_div)

            with ui.row().classes("justify-end w-full gap-2 mt-3"):
                def _dl():
                    try:
                        pdf = _paper_pdf_bytes(full_html, is_rtl())
                        tmp = tempfile.NamedTemporaryFile(
                            delete=False, suffix=".pdf").name
                        with open(tmp, "wb") as f:
                            f.write(pdf)
                        ui.download(tmp,
                                    filename=f"hubx_paper_{title[:30]}.pdf")
                        ui.timer(15.0, lambda: _safe_unlink(tmp), once=True)
                    except Exception as e:
                        ui.notify(f"PDF failed: {e}", color="negative")

                def _print():
                    try:
                        pdf = _paper_pdf_bytes(full_html, is_rtl())
                        token = _cache_paper_pdf(pdf)
                        ui.run_javascript(
                            f"window.open('/paper/{token}', '_blank');"
                        )
                    except Exception as e:
                        ui.notify(f"Print failed: {e}", color="negative")

                ui.button("🖨 Print", on_click=_print).classes(
                    "hubx-btn hubx-btn-primary")
                ui.button(t("download_pdf"), on_click=_dl).classes(
                    "hubx-btn hubx-btn-danger")
                ui.button(t("close"), on_click=d.close).classes(
                    "hubx-btn hubx-btn-ghost")
    d.open()


def _safe_unlink(p):
    try:
        os.unlink(p)
    except Exception:
        pass


@ui.page("/")
def check_page():
    STATE.lang = app.storage.user.get("lang", STATE.lang)
    STATE.focus = app.storage.user.get("focus", STATE.focus)
    _apply_body_class()

    _header()
    _db_banner()

    with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
        ui.label(t("check_title")).classes("hubx-title")
        ui.label(t("check_sub")).classes("hubx-subtitle")

        state = {"result": {}, "filename": "", "original_text": "",
                 "file_type": "", "extracted": False}

        with ui.card().classes("hubx-card w-full"):
            ui.label(t("step1")).classes("font-bold text-base mb-2")
            upload_status = ui.label(t("no_file")).classes(
                "text-sm").style("color:var(--hubx-text-dim)")

            async def handle_upload(e):
                data = await e.content.read()
                filename = e.name or "upload"
                ext = os.path.splitext(filename)[1].lower()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
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

        with ui.card().classes("hubx-card w-full"):
            ui.label(t("step2")).classes("font-bold text-base mb-2")
            err_label = ui.label("").style("color:#ef4a5e")
            analyze_btn = ui.button(t("analyze_now")).classes(
                "hubx-btn hubx-btn-accent")
            progress = ui.linear_progress(value=0, show_value=False).classes(
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
                    err_label.text = f"Gemini error: {gemini_mod.last_error}"
                    ui.notify("Analysis failed.", color="red")
                    return
                state["result"] = result
                render_result()
                try:
                    save_check_report(
                        state["filename"], state["file_type"],
                        state["original_text"],
                        result.get("issues", []),
                        float(result.get("score", 0.0)),
                        result.get("summary", ""))
                except Exception as ex:
                    ui.notify(f"Save failed: {ex}", color="orange")
                ui.notify(f"Found {len(result.get('issues', []))} issue(s).",
                          color="green")

            analyze_btn.on("click", do_analyze)

        with ui.card().classes("hubx-card w-full"):
            ui.label(t("step3")).classes("font-bold text-base mb-2")
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

        def render_result():
            result = state["result"]
            score = float(result.get("score", 0.0))
            score_label.text = f"Score: {score:.2f} / 1.00"
            score_label.style(
                "color: #22d3a6" if score >= 0.7 else "color: #ef4a5e")
            summary_box.content = result.get("summary", "")
            issues_table.rows = result.get("issues", []) or []

        def dl_txt():
            if not state["result"]:
                ui.notify("Analyze first", color="orange"); return
            ui.download(build_txt(state["filename"], state["result"]),
                        filename="hubx_report.txt")

        def dl_pdf():
            if not state["result"]:
                ui.notify("Analyze first", color="orange"); return
            ui.download(build_pdf(state["filename"], state["result"]),
                        filename="hubx_report.pdf")

        def dl_xlsx():
            if not state["result"]:
                ui.notify("Analyze first", color="orange"); return
            ui.download(build_xlsx(state["filename"], state["result"]),
                        filename="hubx_report.xlsx")

        with ui.row().classes("gap-2 mt-3 flex-wrap"):
            ui.button(t("dl_txt"), on_click=dl_txt).classes(
                "hubx-btn hubx-btn-ghost")
            ui.button(t("dl_pdf"), on_click=dl_pdf).classes(
                "hubx-btn hubx-btn-danger")
            ui.button(t("dl_xlsx"), on_click=dl_xlsx).classes(
                "hubx-btn hubx-btn-primary")


@ui.page("/knowledge")
def knowledge_page():
    STATE.lang = app.storage.user.get("lang", STATE.lang)
    STATE.focus = app.storage.user.get("focus", STATE.focus)
    _apply_body_class()
    _header()
    _db_banner()

    selected = {"cat": None}

    drawer_cls = ui.right_drawer if is_rtl() else ui.left_drawer
    with drawer_cls(value=False, bordered=True).classes("hubx-drawer") as kdrawer:
        with ui.column().classes("w-full p-3 gap-1"):
            ui.label(t("categories")).classes("font-bold text-base")
            cat_container = ui.column().classes("w-full gap-1")
            ui.separator().style("border-color:var(--hubx-border)")
            ui.label(t("topics")).classes("font-bold text-base mt-2")
            topic_label = ui.label("").classes("text-xs").style(
                "color:var(--hubx-text-dim)")
            topic_container = ui.column().classes("w-full gap-0.5")

    with ui.column().classes("w-full p-2 gap-3"):
        ui.label(t("knowledge_title")).classes("hubx-title")
        ui.label(t("knowledge_sub")).classes("hubx-subtitle")

        with ui.card().classes("hubx-card w-full"):
            ui.label(t("ai_search")).classes("font-bold text-base mb-2")
            with ui.row().classes("w-full gap-2 items-center no-wrap"):
                q_input = ui.input(placeholder=t("ask_ph")).classes("flex-1")
                ask_btn = ui.button(t("ask")).classes("hubx-btn hubx-btn-primary")
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
                    search_status.text = f"AI error: {gemini_mod.last_error}"
                    return
                search_status.text = ""
                search_answer.content = answer

            ask_btn.on("click", do_search)
            q_input.on("keydown.enter", do_search)

        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.button("☰  " + t("browse"),
                      on_click=lambda: kdrawer.set_value(not kdrawer.value)
                      ).classes("hubx-btn hubx-btn-ghost")

        reader_toolbar = ui.row().classes(
            "w-full gap-2 items-center flex-wrap")
        detail = ui.markdown(t("no_selection")).classes(
            "hubx-body w-full")

    def show_item(kid):
        k = get_knowledge_by_id(kid)
        if not k:
            return
        body = k[4] or k[3] or "(empty)"
        detail.content = (f"# {k[1]}\n\n"
                          f"**{t('category')}:** {k[2]}  ·  "
                          f"**{t('version')}:** v{k[5]}  ·  "
                          f"**{t('confidence')}:** {round(k[6] or 0, 2)}\n\n"
                          f"---\n\n{body}")
        reader_toolbar.clear()
        with reader_toolbar:
            ui.button(t("btn_pdf"), on_click=lambda: ui.download(
                topic_pdf(k[1], k[2], k[5], body),
                filename=f"hubx_{k[1][:30]}.pdf")
            ).classes("hubx-btn hubx-btn-danger")
            ui.button(t("btn_docx"), on_click=lambda: ui.download(
                topic_docx(k[1], k[2], k[5], body),
                filename=f"hubx_{k[1][:30]}.docx")
            ).classes("hubx-btn hubx-btn-primary")
            ui.button(t("btn_txt"), on_click=lambda: ui.download(
                topic_txt(k[1], k[2], k[5], body),
                filename=f"hubx_{k[1][:30]}.txt")
            ).classes("hubx-btn hubx-btn-ghost")
            ui.button(t("preview_paper"),
                      on_click=lambda: _open_paper_dialog(
                          k[1], k[2], k[5], body, {})
            ).classes("hubx-btn hubx-btn-accent")
        kdrawer.set_value(False)

    def render_topics():
        topic_container.clear()
        cat = selected["cat"]
        rows = get_all_knowledge(category=cat, limit=1000)
        topic_label.text = (f"{len(rows)} {t('topics')}"
                            if cat else f"{len(rows)} {t('all_topics')}")
        with topic_container:
            if not rows:
                ui.label("(empty)").classes("italic text-xs").style(
                    "color:var(--hubx-text-dim);padding:8px")
            for r in rows[:300]:
                kid, topic, ver = r[0], r[1], r[5]
                b = ui.button(f"{topic[:60]}  ·  v{ver}").classes(
                    "hubx-drawer-btn")
                b.on("click", lambda k=kid: show_item(k))

    def render_categories():
        cat_container.clear()
        counts = category_counts()
        with cat_container:
            b = ui.button(t("all_topics")).classes(
                "hubx-drawer-btn" +
                (" selected" if selected["cat"] is None else ""))
            b.on("click", lambda: select_category(None))
            for cat, n in counts:
                cls = "hubx-drawer-btn" + (
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


@ui.page("/templates")
def templates_page():
    STATE.lang = app.storage.user.get("lang", STATE.lang)
    STATE.focus = app.storage.user.get("focus", STATE.focus)
    _apply_body_class()
    _header()
    _db_banner()

    tstats = template_stats()
    selected = {"cat": None}

    drawer_cls = ui.right_drawer if is_rtl() else ui.left_drawer
    with drawer_cls(value=False, bordered=True).classes("hubx-drawer") as tdrawer:
        with ui.column().classes("w-full p-3 gap-1"):
            ui.label(t("categories")).classes("font-bold text-base")
            cat_container = ui.column().classes("w-full gap-1")
            ui.separator().style("border-color:var(--hubx-border)")
            ui.label(t("templates_word")).classes("font-bold text-base mt-2")
            topic_label = ui.label("").classes("text-xs").style(
                "color:var(--hubx-text-dim)")
            t_container = ui.column().classes("w-full gap-0.5")

    with ui.column().classes("w-full p-2 gap-3"):
        ui.label(t("templates_title")).classes("hubx-title")
        ui.label(t("templates_sub")).classes("hubx-subtitle")

        with ui.row().classes("gap-3 mb-2 flex-wrap"):
            _stat(t("templates_word")).text = str(tstats["total"])
            _stat(t("refined_word")).text = str(tstats["refined"])
            _stat(t("queue_word")).text = str(tstats["pending"])

        with ui.row().classes("w-full items-center gap-2 mt-2"):
            ui.button("☰  " + t("browse"),
                      on_click=lambda: tdrawer.set_value(not tdrawer.value)
                      ).classes("hubx-btn hubx-btn-ghost")

        toolbar = ui.row().classes(
            "w-full gap-2 items-center flex-wrap")
        detail = ui.markdown(t("no_selection")).classes(
            "hubx-body w-full")

    def show_template(tid):
        tmpl = get_template_by_id(tid)
        if not tmpl:
            return
        body = tmpl[4] or tmpl[3] or "(empty)"
        detail.content = (f"# {tmpl[1]}\n\n"
                          f"**{t('category')}:** {tmpl[2]}  ·  "
                          f"**{t('version')}:** v{tmpl[5]}  ·  "
                          f"**{t('confidence')}:** {round(tmpl[6] or 0, 2)}\n\n"
                          f"---\n\n{body}")
        toolbar.clear()
        with toolbar:
            ui.button(t("btn_pdf"), on_click=lambda: ui.download(
                topic_pdf(tmpl[1], tmpl[2], tmpl[5], body),
                filename=f"hubx_tpl_{tmpl[1][:30]}.pdf")
            ).classes("hubx-btn hubx-btn-danger")
            ui.button(t("btn_docx"), on_click=lambda: ui.download(
                topic_docx(tmpl[1], tmpl[2], tmpl[5], body),
                filename=f"hubx_tpl_{tmpl[1][:30]}.docx")
            ).classes("hubx-btn hubx-btn-primary")
            ui.button(t("btn_txt"), on_click=lambda: ui.download(
                topic_txt(tmpl[1], tmpl[2], tmpl[5], body),
                filename=f"hubx_tpl_{tmpl[1][:30]}.txt")
            ).classes("hubx-btn hubx-btn-ghost")
            ui.button(t("preview_paper"),
                      on_click=lambda: _open_paper_dialog(
                          tmpl[1], tmpl[2], tmpl[5], body, {})
            ).classes("hubx-btn hubx-btn-accent")
        tdrawer.set_value(False)

    def render_templates():
        t_container.clear()
        cat = selected["cat"]
        rows = get_all_templates(category=cat, limit=500)
        topic_label.text = f"{len(rows)} {t('templates_word')}"
        with t_container:
            if not rows:
                ui.label("(empty)").classes("italic text-xs").style(
                    "color:var(--hubx-text-dim);padding:8px")
            for r in rows[:300]:
                tid, name, ver = r[0], r[1], r[5]
                b = ui.button(f"{name[:60]}  ·  v{ver}").classes(
                    "hubx-drawer-btn")
                b.on("click", lambda t_=tid: show_template(t_))

    def render_cats():
        cat_container.clear()
        counts = template_category_counts()
        with cat_container:
            b = ui.button(t("all_categories")).classes(
                "hubx-drawer-btn" +
                (" selected" if selected["cat"] is None else ""))
            b.on("click", lambda: sel(None))
            for cat, n in counts:
                cls = "hubx-drawer-btn" + (
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


@ui.page("/charts")
def charts_page():
    STATE.lang = app.storage.user.get("lang", STATE.lang)
    STATE.focus = app.storage.user.get("focus", STATE.focus)
    _apply_body_class()
    _header()
    _db_banner()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-3"):
        ui.label(t("charts_title")).classes("hubx-title")
        ui.label(t("charts_sub")).classes("hubx-subtitle")

        import matplotlib
        matplotlib.use("Agg")

        with ui.row().classes("w-full gap-3 flex-wrap"):
            c1 = ui.matplotlib(figsize=(6, 4)).classes(
                "hubx-card w-[48%] h-80")
            c2 = ui.matplotlib(figsize=(6, 4)).classes(
                "hubx-card w-[48%] h-80")
            c3 = ui.matplotlib(figsize=(10, 4)).classes(
                "hubx-card w-full h-80")
            c4 = ui.matplotlib(figsize=(10, 4)).classes(
                "hubx-card w-full h-80")

        def style_ax(ax):
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
            style_ax(ax)
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
            style_ax(ax)
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
            style_ax(ax)
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
            ax.plot(cycles, added, marker="o", color="#4f8cff", label="added")
            ax.plot(cycles, refined, marker="s", color="#ef4a5e",
                    label="refined")
            ax.set_title("Learning activity")
            style_ax(ax)
            leg = ax.legend(facecolor="#131a2f", edgecolor="#2a3559")
            for t_ in leg.get_texts():
                t_.set_color("#e8ecf7")
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


@ui.page("/dashboard")
def dashboard_page():
    STATE.lang = app.storage.user.get("lang", STATE.lang)
    STATE.focus = app.storage.user.get("focus", STATE.focus)
    _apply_body_class()
    _header()
    _db_banner()

    with ui.column().classes("w-full max-w-7xl mx-auto p-4 gap-3"):
        ui.label(t("dash_title")).classes("hubx-title")

        with ui.row().classes("gap-3 items-center flex-wrap"):
            status_badge = ui.badge("idle", color="grey").classes("text-sm")
            cycles_label = _stat(t("cycles"))
            gemini_label = _stat(t("gemini_calls"))
            kb_label = _stat(t("knowledge_stat"))
            refined_label = _stat(t("refined_stat"))
            tpl_label = _stat(t("templates_stat"))
            queue_label = _stat(t("queue_stat"))

        debug_label = ui.label("").classes("text-sm").style(
            "color:var(--hubx-text-dim)")
        gemini_err_label = ui.label("").style(
            "color:#ffc270;font-size:0.85rem")
        quota_label = ui.label("").style(
            "color:var(--hubx-text-dim);font-size:0.82rem")

        async def do_start():
            await engine.start(by_user=True)
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

        with ui.row().classes("gap-2 mt-2 flex-wrap"):
            ui.button(t("start"), on_click=do_start).classes(
                "hubx-btn hubx-btn-accent")
            ui.button(t("pause"), on_click=do_pause).classes(
                "hubx-btn hubx-btn-warn")
            ui.button(t("one_cycle"), on_click=do_one_cycle).classes(
                 "hubx-btn hubx-btn-primary")

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
            try:
                q = gemini_usage_stats()
                quota_label.text = (
                    f"Gemini usage — last 1h: {q['last_1h']}/{q['hour_limit']}"
                    f"  ·  last 24h: {q['last_24h']}/{q['day_limit']}")
            except Exception:
                quota_label.text = ""

        ui.timer(2.0, refresh)
        refresh()

        ui.label(t("recent_runs")).classes("text-lg font-bold mt-4")
        runs_table = ui.table(columns=[
            {"name": "cycle", "label": t("cycles"), "field": "cycle"},
            {"name": "topic", "label": "Topic", "field": "topic",
             "align": "left"},
            {"name": "added", "label": "+", "field": "added"},
            {"name": "refined", "label": "~", "field": "refined"},
            {"name": "calls", "label": "Calls", "field": "calls"},
            {"name": "error", "label": "Error", "field": "error"},
            {"name": "created_at", "label": "When", "field": "created_at"},
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

        ui.label(t("recent_tpl_runs")).classes("text-lg font-bold mt-4")
        tpl_table = ui.table(columns=[
            {"name": "cycle", "label": t("cycles"), "field": "cycle"},
            {"name": "name", "label": t("templates_word"), "field": "name",
             "align": "left"},
            {"name": "added", "label": "+", "field": "added"},
            {"name": "refined", "label": "~", "field": "refined"},
            {"name": "error", "label": "Error", "field": "error"},
            {"name": "created_at", "label": "When", "field": "created_at"},
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


ui.run(host="0.0.0.0", port=PORT, reload=False, title="HUBx",
       storage_secret=os.getenv("STORAGE_SECRET", "hubx-dev-secret"))
