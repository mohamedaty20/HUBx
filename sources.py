# sources.py
# Seed topics for the self-learning loop. The engine cycles through these
# and asks Gemini to generate or refine knowledge on each one.
# Categories follow Egyptian civil quality engineering practice.

SEED_TOPICS = [
    # Concrete
    ("Concrete mix design and water/cement ratio limits", "concrete"),
    ("Concrete curing duration and methods per ECP 203", "concrete"),
    ("Concrete cube testing frequency and acceptance criteria", "concrete"),
    ("Slump test procedure and acceptance limits", "concrete"),
    ("Hot weather concreting precautions in Egypt", "concrete"),
    ("Formwork stripping times and safety", "concrete"),
    ("Reinforcement cover requirements per exposure class", "concrete"),
    ("Concrete surface defects: causes and repair", "concrete"),

    # Steel
    ("Reinforcement bar inspection before pouring", "steel"),
    ("Lap length and anchorage requirements per ECP 205", "steel"),
    ("Welding quality control for steel structures", "steel"),
    ("Steel corrosion protection and galvanizing", "steel"),

    # Soil and foundations
    ("Soil compaction testing: proctor and field density", "soil"),
    ("Plate load test procedure and interpretation", "soil"),
    ("Pile integrity testing methods", "soil"),
    ("Foundation excavation inspection checklist", "soil"),

    # Water and infrastructure
    ("Water pipeline pressure testing procedure", "water"),
    ("Sanitary sewer installation quality checks", "water"),
    ("Waterproofing of underground structures", "water"),
    ("Pump station commissioning checklist", "water"),

    # Quality management
    ("ITP (Inspection and Test Plan) development", "quality_management"),
    ("Non-conformance report (NCR) handling", "quality_management"),
    ("Material submittal and approval workflow", "quality_management"),
    ("Site quality audit checklist", "quality_management"),
    ("Document control and revision management", "quality_management"),
    ("Method statement review criteria", "quality_management"),

    # Roads and asphalt
    ("Asphalt paving temperature and compaction checks", "roads"),
    ("Subbase and base course acceptance criteria", "roads"),
    ("Road marking and signage quality standards", "roads"),

    # Egyptian codes
    ("Egyptian Code ECP 203: concrete design and quality", "egyptian_codes"),
    ("Egyptian Code ECP 204: steel construction quality", "egyptian_codes"),
    ("Egyptian Code ECP 202: soil mechanics and foundations", "egyptian_codes"),
    ("Egyptian Standard Specifications for materials", "egyptian_codes"),
]

# Egyptian quality authorities and references the AI should cite.
EGYPT_REFERENCES = [
    "Egyptian Code for Design and Construction of Concrete Structures (ECP 203)",
    "Egyptian Code for Steel Construction (ECP 205)",
    "Egyptian Code for Soil Mechanics and Foundations (ECP 202)",
    "Egyptian Standard Specifications (ESS)",
    "Housing and Building National Research Center (HBRC)",
    "Egyptian Organization for Standardization and Quality (EOS)",
    "Ministry of Housing, Utilities and Urban Communities",
]

LEARNING_INTERVAL_SECONDS = 20
REFINE_EVERY_N_CYCLES = 2          # refine existing knowledge every other cycle
MAX_KNOWLEDGE_ITEMS = 500          # cap to protect free-tier memory
