# sources.py
# Seed topics + template categories. Engine EXPANDS this list dynamically.

LEARNING_INTERVAL_SECONDS = 20
REFINE_EVERY_N_CYCLES = 4
SUGGESTIONS_PER_CYCLE = 3
MAX_KNOWLEDGE_ITEMS = 2000
TEMPLATE_INTERVAL_SECONDS = 30
MAX_TEMPLATES = 400

SEED_TOPICS = [
    # ---- concrete ----
    ("Concrete mix design and water/cement ratio limits", "concrete"),
    ("Concrete curing duration and methods per ECP 203", "concrete"),
    ("Concrete cube testing frequency and acceptance", "concrete"),
    ("Slump test procedure and acceptance limits", "concrete"),
    ("Hot weather concreting precautions in Egypt", "concrete"),
    ("Cold weather concreting precautions", "concrete"),
    ("Formwork stripping times and safety", "concrete"),
    ("Reinforcement cover requirements per exposure class", "concrete"),
    ("Concrete surface defects: causes and repair", "concrete"),
    ("Self-compacting concrete quality checks", "concrete"),
    ("Ready-mix concrete delivery and acceptance", "concrete"),
    ("Concrete pumping quality control", "concrete"),
    ("Concrete admixtures: types and dosage limits", "concrete"),
    ("Concrete permeability and durability tests", "concrete"),
    ("Chloride and sulfate attack on concrete", "concrete"),
    ("Shrinkage cracks: control and repair", "concrete"),
    ("Thermal cracking in mass concrete", "concrete"),
    ("Concrete repair materials and methods", "concrete"),
    ("Concrete surface preparation for finishes", "concrete"),
    ("Lightweight concrete quality control", "concrete"),

    # ---- steel ----
    ("Reinforcement bar inspection before pouring", "steel"),
    ("Lap length and anchorage per ECP 205", "steel"),
    ("Welding quality control for steel structures", "steel"),
    ("Steel corrosion protection and galvanizing", "steel"),
    ("Bolted connections torque and inspection", "steel"),
    ("Post-tensioning quality control", "steel"),
    ("Rebar bending and cutting tolerances", "steel"),
    ("Structural steel fabrication tolerances", "steel"),
    ("Fireproofing of steel structures", "steel"),
    ("Rebar couplers and mechanical splices", "steel"),

    # ---- soil ----
    ("Soil compaction testing: proctor and field density", "soil"),
    ("Plate load test procedure and interpretation", "soil"),
    ("Pile integrity testing methods", "soil"),
    ("Foundation excavation inspection checklist", "soil"),
    ("Soil bearing capacity determination", "soil"),
    ("Ground improvement techniques", "soil"),
    ("Settlement monitoring and limits", "soil"),
    ("Retaining wall backfill requirements", "soil"),
    ("Slope stability assessment", "soil"),
    ("Dewatering systems and quality control", "soil"),
    ("Shallow foundation inspection", "soil"),
    ("Deep foundation construction QC", "soil"),

    # ---- water ----
    ("Water pipeline pressure testing procedure", "water"),
    ("Sanitary sewer installation quality checks", "water"),
    ("Waterproofing of underground structures", "water"),
    ("Pump station commissioning checklist", "water"),
    ("Water tank leakage testing", "water"),
    ("Pipeline bedding and backfill requirements", "water"),
    ("Manhole construction standards", "water"),
    ("Wastewater treatment plant quality control", "water"),
    ("Irrigation canal lining quality", "water"),
    ("Stormwater drainage quality", "water"),

    # ---- roads ----
    ("Asphalt paving temperature and compaction checks", "roads"),
    ("Subbase and base course acceptance criteria", "roads"),
    ("Road marking and signage quality standards", "roads"),
    ("Asphalt mix design verification", "roads"),
    ("Concrete pavement jointing", "roads"),
    ("Road drainage quality control", "roads"),
    ("Geotextile installation inspection", "roads"),
    ("Interlocking tile laying quality", "roads"),
    ("Curb and gutter installation quality", "roads"),
    ("Bridge deck waterproofing", "roads"),

    # ---- quality_management ----
    ("ITP (Inspection and Test Plan) development", "quality_management"),
    ("Non-conformance report handling", "quality_management"),
    ("Material submittal and approval workflow", "quality_management"),
    ("Site quality audit checklist", "quality_management"),
    ("Document control and revision management", "quality_management"),
    ("Method statement review criteria", "quality_management"),
    ("Snag list management and closeout", "quality_management"),
    ("Handover documentation checklist", "quality_management"),
    ("Subcontractor quality evaluation", "quality_management"),
    ("KPI tracking for site quality", "quality_management"),
    ("Mock-up approval process", "quality_management"),
    ("Sample and prototype testing", "quality_management"),
    ("RFI (Request for Information) handling", "quality_management"),
    ("Warranty and defect liability periods", "quality_management"),
    ("Quality closeout procedures", "quality_management"),
    ("Corrective and preventive actions", "quality_management"),
    ("Root cause analysis for defects", "quality_management"),
    ("Quality training programs", "quality_management"),

    # ---- egyptian_codes ----
    ("Egyptian Code ECP 203: concrete design and quality", "egyptian_codes"),
    ("Egyptian Code ECP 204: steel construction quality",
     "egyptian_codes"),
    ("Egyptian Code ECP 202: soil mechanics and foundations",
     "egyptian_codes"),
    ("Egyptian Standard Specifications for materials", "egyptian_codes"),
    ("HBRC guidelines and approvals", "egyptian_codes"),
    ("Egyptian fire code requirements", "egyptian_codes"),
    ("Egyptian building code seismic provisions", "egyptian_codes"),
    ("Egyptian electrical code for buildings", "egyptian_codes"),
    ("Building permit requirements Egypt", "egyptian_codes"),
    ("Egyptian plumbing code requirements", "egyptian_codes"),

    # ---- safety ----
    ("Excavation shoring and safety", "safety"),
    ("Scaffolding inspection checklist", "safety"),
    ("Lifting operations and crane inspection", "safety"),
    ("Confined space entry procedures", "safety"),
    ("Fall protection requirements", "safety"),
    ("Hot work permit procedures", "safety"),
    ("Site PPE requirements", "safety"),
    ("Emergency response planning", "safety"),
    ("Hazard identification and risk assessment", "safety"),
    ("Working at height safety", "safety"),

    # ---- surveying ----
    ("Setting out accuracy checks", "surveying"),
    ("As-built surveying requirements", "surveying"),
    ("Total station calibration and use", "surveying"),
    ("Surveying level and verticality tolerances", "surveying"),
    ("Dimensional control for structures", "surveying"),
    ("Grid line establishment and verification", "surveying"),
    ("Benchmark establishment and monitoring", "surveying"),
]

# ------------------------------------------------------------------
# Egyptian construction site paper templates
# ------------------------------------------------------------------

TEMPLATE_CATEGORIES = [
    ("administrative", "Administrative (إداري)"),
    ("quality", "Quality Control (جودة)"),
    ("safety", "Safety & Health (سلامة)"),
    ("technical", "Technical / Site (فني)"),
    ("financial", "Financial (مالي)"),
    ("legal", "Permits & Legal (قانوني)"),
    ("handover", "Handover & Closeout (تسليم)"),
]

SEED_TEMPLATES = [
    # Administrative
    ("Notice for Work Start (إخطار بدء أعمال)", "administrative"),
    ("Inspection Request (طلب فحص أعمال)", "administrative"),
    ("Document Approval Request (طلب اعتماد مستندات)",
     "administrative"),
    ("Sub Contractor Approval (اعتماد مقاول باطن)", "administrative"),
    ("Request for Information - RFI (طلب معلومات)", "administrative"),
    ("Variation Order (طلب تعديل / إضافة أعمال)", "administrative"),
    ("Meeting Minutes (محضر اجتماع)", "administrative"),
    ("Site Work Instructions (تعليمات موقع)", "administrative"),
    ("Transmittal Form (نموذج إرسال مستندات)", "administrative"),
    ("Site Diary / Daily Report (التقرير اليومي)", "administrative"),

    # Quality
    ("Inspection and Test Plan - ITP (خطة الفحص والاختبار)",
     "quality"),
    ("Non-Conformance Report - NCR (تقرير عدم مطابقة)", "quality"),
    ("Material Inspection Request - MIR (طلب فحص مواد)", "quality"),
    ("Work Inspection Request - WIR (طلب فحص أعمال)", "quality"),
    ("Method Statement Template (بيان طريقة العمل)", "quality"),
    ("Material Submittal Form (نموذج اعتماد مواد)", "quality"),
    ("Concrete Pour Record (بيان صب خرسانة)", "quality"),
    ("Test Results Summary (ملخص نتائج الاختبارات)", "quality"),
    ("Quality Audit Report (تقرير مراجعة الجودة)", "quality"),
    ("Snag List / Punch List (قائمة الملاحظات)", "quality"),

    # Safety
    ("Safety Inspection Checklist (قائمة فحص السلامة)", "safety"),
    ("Toolbox Talk Record (سجل اجتماع السلامة)", "safety"),
    ("Permit to Work (تصريح عمل)", "safety"),
    ("Incident Report (تقرير حادث)", "safety"),
    ("Risk Assessment Form (نموذج تقييم مخاطر)", "safety"),
    ("PPE Compliance Record (سجل الالتزام بمعدات الوقاية)",
     "safety"),
    ("Emergency Evacuation Plan (خطة إخلاء طوارئ)", "safety"),
    ("Safety Observation Report (تقرير ملاحظات السلامة)",
     "safety"),

    # Technical
    ("Site Inspection Report (محضر معاينة موقع)", "technical"),
    ("Soil Report Template (تقرير التربة)", "technical"),
    ("Setting Out Record (سجل توقيع المحاور)", "technical"),
    ("As-Built Drawing Record (سجل الرسومات التنفيذية)",
     "technical"),
    ("Shop Drawing Submittal (تقديم لوحات تفصيلية)", "technical"),
    ("Technical Query Form (استفسار فني)", "technical"),
    ("Site Measurement Sheet (ورقة قياسات موقع)", "technical"),
    ("Construction Progress Report (تقرير تقدم الأعمال)",
     "technical"),

    # Financial
    ("Interim Payment Certificate (مستخلص أعمال)", "financial"),
    ("Purchase Order - PO (طلب شراء)", "financial"),
    ("Material Requisition Form (طلب صرف مواد)", "financial"),
    ("Labour Return Form (سجل عمالة يومي)", "financial"),
    ("Equipment Log (سجل معدات)", "financial"),
    ("Cost Variation Claim (مطالبة بتكلفة إضافية)", "financial"),

    # Legal / Permits
    ("Building Permit Application (طلب ترخيص بناء)", "legal"),
    ("Site Validity Certificate (شهادة صلاحية موقع)", "legal"),
    ("Construction Value Form (نموذج حساب قيمة الأعمال)",
     "legal"),
    ("Insurance Certificate (شهادة تأمين)", "legal"),
    ("Building Completion Certificate (شهادة إتمام بناء)",
     "legal"),

    # Handover
    ("Handover Checklist (قائمة التسليم)", "handover"),
    ("Warranty Certificate (شهادة ضمان)", "handover"),
    ("Defects Liability Record (سجل فترة الضمان)", "handover"),
    ("Operation and Maintenance Manual (دليل التشغيل والصيانة)",
     "handover"),
    ("As-Built Document Register (سجل المستندات النهائية)",
     "handover"),
]

SUGGEST_TOPICS_SYSTEM = (
    "You are a curriculum designer for Egyptian civil quality engineering. "
    "Given a topic the student just finished, propose NEW related sub-topics "
    "that are different from the parent. Focus on specifics that an Egyptian "
    "site engineer would actually need on site. "
    "Return ONLY a JSON object with a single key called subtopics whose value "
    "is an array of objects. Each object has a topic string and a category "
    "string. "
    "The category must be one of: concrete, steel, soil, water, roads, "
    "quality_management, egyptian_codes, safety, surveying. "
    "No LaTeX. No dollar signs. No markdown fences."
)

SUGGEST_TOPICS_USER = (
    "Parent topic: {topic}\n"
    "Parent category: {category}\n\n"
    "Propose exactly {n} new sub-topics in the same or closely related "
    "category. Each sub-topic must be a specific, checkable engineering "
    "topic with a clear title under 80 characters."
)

SUGGEST_TEMPLATES_SYSTEM = (
    "You are a document control specialist for Egyptian construction "
    "companies. Given a template name and category, propose NEW related "
    "site paper templates that are used on Egyptian construction sites. "
    "Return ONLY a JSON object with a single key called templates whose "
    "value is an array of objects. Each object has a name string and a "
    "category string. "
    "Category must be one of: administrative, quality, safety, technical, "
    "financial, legal, handover. "
    "No LaTeX. No dollar signs. No markdown fences."
)

SUGGEST_TEMPLATES_USER = (
    "Parent template: {name}\n"
    "Parent category: {category}\n\n"
    "Propose exactly {n} new site paper templates. Each must have a clear "
    "title under 80 characters that includes both English and Arabic names "
    "where possible."
)


# ==================================================================
# COMPLIANCE WHITELIST
# ==================================================================
# The block below is what compliance.py imports. It lives here so the
# project has a single sources.py. It does NOT replace or touch any
# of the learning/template constants above.
# ==================================================================

# Seconds between two live requests to the same domain.
MIN_DOMAIN_DELAY = 3.0

# Honest User-Agent sent with every live fetch.
USER_AGENT = (
    "EgyptCivilEngJobBot/1.0 "
    "(+contact: your-email@example.com) "
    "Python-httpx/0.28"
)

# Tier A: official API / RSS. Safe for live fetch, no robots.txt dance.
TIER_A = [
    "arbeitnow.com",
    "remoteok.com",
    "weworkremotely.com",
]

# Tier B: HTML pages you have personally verified (robots.txt allows,
# ToS does not forbid). Leave empty until you verify a domain yourself.
TIER_B = [
    # "example-engineering-company.com",
]

# Tier C: ToS forbids scraping -> manual paste only.
TIER_C = [
    "wuzzuf.net",
    "bayt.com",
    "tanqeeb.com",
    "linkedin.com",
    "indeed.com",
    "forasna.com",
    "gulftalent.com",
    "naukrigulf.com",
    "careerjet.com.eg",
]

# Tier D: blocked (bot protection / legal block).
TIER_D = [
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "threads.net",
]

# Internal lookup table built once at import.
_TIER_MAP = {}
for _d in TIER_A:
    _TIER_MAP[_d] = "A"
for _d in TIER_B:
    _TIER_MAP[_d] = "B"
for _d in TIER_C:
    _TIER_MAP[_d] = "C"
for _d in TIER_D:
    _TIER_MAP[_d] = "D"

# Domains that need a slower crawl than MIN_DOMAIN_DELAY.
_DELAY_OVERRIDES = {
    "linkedin.com": 30.0,
    "indeed.com":   20.0,
    "bayt.com":     10.0,
    "wuzzuf.net":   10.0,
    "tanqeeb.com":  10.0,
}


def _norm_domain(domain: str) -> str:
    if not domain:
        return ""
    d = domain.lower().strip()
    d = d.removeprefix("http://").removeprefix("https://")
    d = d.removeprefix("www.")
    d = d.split("/")[0]
    return d


def get_tier(domain: str) -> str:
    """Return 'A' | 'B' | 'C' | 'D' | 'unknown'."""
    d = _norm_domain(domain)
    if not d:
        return "unknown"
    if d in _TIER_MAP:
        return _TIER_MAP[d]
    # try parent domains (sub.example.com -> example.com)
    parts = d.split(".")
    for i in range(1, len(parts)):
        parent = ".".join(parts[i:])
        if parent in _TIER_MAP:
            return _TIER_MAP[parent]
    return "unknown"


def get_min_delay(domain: str) -> float:
    """Seconds to wait before hitting this domain again."""
    d = _norm_domain(domain)
    if d in _DELAY_OVERRIDES:
        return _DELAY_OVERRIDES[d]
    for parent, delay in _DELAY_OVERRIDES.items():
        if d == parent or d.endswith("." + parent):
            return delay
    return MIN_DOMAIN_DELAY


def all_domains() -> list:
    """Every whitelisted domain, any tier."""
    return list(_TIER_MAP.keys())


def allowed_domains() -> list:
    """Domains safe for live fetch (tiers A and B only)."""
    return list(TIER_A) + list(TIER_B)


def blocked_domains() -> list:
    """Domains that must not be fetched live (tiers C and D)."""
    return list(TIER_C) + list(TIER_D)


def is_allowed(domain: str, kind: str = "fetch") -> bool:
    """
    kind='fetch' -> only A and B pass (live network).
    kind='parse' -> A, B, and C pass (user pasted the content).
    """
    tier = get_tier(domain)
    if kind == "parse":
        return tier in ("A", "B", "C")
    return tier in ("A", "B")


def tier_label(tier: str) -> str:
    """Human-readable label for the UI."""
    return {
        "A": "API / RSS",
        "B": "HTML (robots-allowed)",
        "C": "Manual paste only",
        "D": "Blocked",
    }.get(tier, "Unknown")


# Sanity check — crashes loudly at import if any of the six names
# compliance.py needs is missing.
assert isinstance(MIN_DOMAIN_DELAY, float)
assert isinstance(USER_AGENT, str)
assert callable(get_tier)
assert callable(get_min_delay)
assert isinstance(TIER_A, list)
assert isinstance(TIER_B, list)
assert isinstance(TIER_C, list)
assert isinstance(TIER_D, list)
