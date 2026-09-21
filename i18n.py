# i18n.py
STRINGS = {
    "en": {
        "title":        "Egypt Civil Engineering — Job Intelligence",
        "focus_label":  "AI Focus",
        "focus_know":   "Knowledge only",
        "focus_tmpl":   "Templates only",
        "focus_both":   "Both",
        "start":        "▶ Start",
        "pause":        "⏸ Pause",
        "lang_en":      "EN",
        "lang_ar":      "ع",
        "tab_dash":     "Dashboards",
        "tab_know":     "Knowledge",
        "tab_tmpl":     "Templates",
        "tab_paste":    "Manual paste",
        "download_pdf": "Download PDF",
        "project_name": "Project Name",
        "engineer":     "Engineer",
        "supervisor":   "Supervisor",
        "date":         "Date",
        "company":      "Company",
        "description":  "Description",
        "preview":      "Preview",
    },
    "ar": {
        "title":        "الذكاء الاصطناعي لوظائف الهندسة المدنية — مصر",
        "focus_label":  "تركيز الذكاء الاصطناعي",
        "focus_know":   "المعرفة فقط",
        "focus_tmpl":   "القوالب فقط",
        "focus_both":   "الاثنان معاً",
        "start":        "▶ ابدأ",
        "pause":        "⏸ إيقاف",
        "lang_en":      "EN",
        "lang_ar":      "ع",
        "tab_dash":     "لوحات المعلومات",
        "tab_know":     "المعرفة",
        "tab_tmpl":     "القوالب",
        "tab_paste":    "لصق يدوي",
        "download_pdf": "تحميل PDF",
        "project_name": "اسم المشروع",
        "engineer":     "المهندس",
        "supervisor":   "المشرف",
        "date":         "التاريخ",
        "company":      "الشركة",
        "description":  "الوصف",
        "preview":      "معاينة",
    },
}

def t(key: str) -> str:
    from state import STATE
    return STRINGS[STATE.lang].get(key, key)

def is_rtl() -> bool:
    from state import STATE
    return STATE.lang == "ar"
