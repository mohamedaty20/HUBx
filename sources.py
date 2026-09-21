# sources.py
# Seed topics + categories. The engine EXPANDS this list by asking Gemini
# for sub-topics, so this is only the starting point.

LEARNING_INTERVAL_SECONDS = 20
REFINE_EVERY_N_CYCLES = 4
SUGGESTIONS_PER_CYCLE = 3
MAX_KNOWLEDGE_ITEMS = 2000

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

    # ---- roads ----
    ("Asphalt paving temperature and compaction checks", "roads"),
    ("Subbase and base course acceptance criteria", "roads"),
    ("Road marking and signage quality standards", "roads"),
    ("Asphalt mix design verification", "roads"),
    ("Concrete pavement jointing", "roads"),
    ("Road drainage quality control", "roads"),
    ("Geotextile installation inspection", "roads"),
    ("Interlocking tile laying quality", "roads"),

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

    # ---- egyptian_codes ----
    ("Egyptian Code ECP 203: concrete design and quality", "egyptian_codes"),
    ("Egyptian Code ECP 204: steel construction quality", "egyptian_codes"),
    ("Egyptian Code ECP 202: soil mechanics and foundations",
     "egyptian_codes"),
    ("Egyptian Standard Specifications for materials", "egyptian_codes"),
    ("HBRC guidelines and approvals", "egyptian_codes"),
    ("Egyptian fire code requirements", "egyptian_codes"),
    ("Egyptian building code seismic provisions", "egyptian_codes"),
    ("Egyptian electrical code for buildings", "egyptian_codes"),

    # ---- safety ----
    ("Excavation shoring and safety", "safety"),
    ("Scaffolding inspection checklist", "safety"),
    ("Lifting operations and crane inspection", "safety"),
    ("Confined space entry procedures", "safety"),
    ("Fall protection requirements", "safety"),
    ("Hot work permit procedures", "safety"),
    ("Site PPE requirements", "safety"),
    ("Emergency response planning", "safety"),

    # ---- surveying ----
    ("Setting out accuracy checks", "surveying"),
    ("As-built surveying requirements", "surveying"),
    ("Total station calibration and use", "surveying"),
    ("Surveying level and verticality tolerances", "surveying"),
    ("Dimensional control for structures", "surveying"),
]

# System prompt with NO curly braces - safe to pass directly.
SUGGEST_TOPICS_SYSTEM = (
    "You are a curriculum designer for Egyptian civil quality engineering. "
    "Given a topic the student just finished, propose NEW related "
    "sub-topics that are different from the parent. Focus on specifics "
    "that an Egyptian site engineer would actually need on site. "
    "Return ONLY a JSON object with a single key called subtopics whose "
    "value is an array of objects. Each object has a topic string and a "
    "category string. "
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
