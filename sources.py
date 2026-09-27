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
    # =========================================================
    # ADMINISTRATIVE (إداري)
    # =========================================================
    ("Notice for Work Start (إخطار بدء أعمال)", "administrative"),
    ("Inspection Request (طلب فحص أعمال)", "administrative"),
    ("Document Approval Request (طلب اعتماد مستندات)", "administrative"),
    ("Sub Contractor Approval (اعتماد مقاول باطن)", "administrative"),
    ("Request for Information - RFI (طلب معلومات)", "administrative"),
    ("Variation Order (طلب تعديل / إضافة أعمال)", "administrative"),
    ("Meeting Minutes (محضر اجتماع)", "administrative"),
    ("Site Work Instructions (تعليمات موقع)", "administrative"),
    ("Transmittal Form (نموذج إرسال مستندات)", "administrative"),
    ("Site Diary / Daily Report (التقرير اليومي)", "administrative"),
    ("Site Instruction Form (نموذج تعليمات الموقع)", "administrative"),
    ("Contractor's Monthly Report (التقرير الشهري للمقاول)", "administrative"),
    ("Progress Report - Weekly (تقرير التقدم الأسبوعي)", "administrative"),
    ("Progress Report - Monthly (تقرير التقدم الشهري)", "administrative"),
    ("Site Meeting Attendance Record (سجل حضور اجتماعات الموقع)", "administrative"),
    ("Correspondence Register (سجل المراسلات)", "administrative"),
    ("Site Visitor Log (سجل زوار الموقع)", "administrative"),
    ("Material Delivery Log (سجل تسليم المواد)", "administrative"),
    ("Equipment Log (سجل المعدات)", "administrative"),
    ("Labour Return Form (سجل العمالة اليومي)", "administrative"),
    ("Site Manpower Report (تقرير القوى العاملة)", "administrative"),
    ("Subcontractor Agreement (اتفاقية مقاول الباطن)", "administrative"),
    ("Scope of Work Document (نطاق العمل)", "administrative"),
    ("Project Charter (ميثاق المشروع)", "administrative"),
    ("Kick-off Meeting Minutes (محضر اجتماع بدء المشروع)", "administrative"),
    ("Internal Memo (مذكرة داخلية)", "administrative"),
    ("Site Instruction Log (سجل تعليمات الموقع)", "administrative"),
    ("Request for Approval of Materials (طلب اعتماد مواد)", "administrative"),
    ("Request for Approval of Shop Drawings (طلب اعتماد الرسومات التنفيذية)", "administrative"),
    ("Technical Query Form (استفسار فني)", "administrative"),
    ("Request for Extension of Time (طلب مد فترة التنفيذ)", "administrative"),
    ("Claim Notice Form (نموذج إخطار بمطالبة)", "administrative"),

    # =========================================================
    # QUALITY CONTROL (جودة)
    # =========================================================
    ("Inspection and Test Plan - ITP (خطة الفحص والاختبار)", "quality"),
    ("Non-Conformance Report - NCR (تقرير عدم مطابقة)", "quality"),
    ("Material Inspection Request - MIR (طلب فحص مواد)", "quality"),
    ("Work Inspection Request - WIR (طلب فحص أعمال)", "quality"),
    ("Method Statement Template (بيان طريقة العمل)", "quality"),
    ("Material Submittal Form (نموذج اعتماد مواد)", "quality"),
    ("Concrete Pour Record (بيان صب خرسانة)", "quality"),
    ("Test Results Summary (ملخص نتائج الاختبارات)", "quality"),
    ("Quality Audit Report (تقرير مراجعة الجودة)", "quality"),
    ("Snag List / Punch List (قائمة الملاحظات)", "quality"),
    ("Concrete Cube Test Report (تقرير اختبار مكعبات الخرسانة)", "quality"),
    ("Slump Test Report (تقرير اختبار الهبوط)", "quality"),
    ("Soil Compaction Test Report (تقرير اختبار دمك التربة)", "quality"),
    ("Field Density Test Report (تقرير اختبار الكثافة الحقلية)", "quality"),
    ("Bitumen Content Test Report (تقرير اختبار نسبة البيتومين)", "quality"),
    ("Marshall Stability Test Report (تقرير اختبار مارشال)", "quality"),
    ("Steel Tensile Test Report (تقرير اختبار الشد للحديد)", "quality"),
    ("Concrete Repair Method Statement (بيان طريقة إصلاح الخرسانة)", "quality"),
    ("Waterproofing Inspection Report (تقرير فحص العزل المائي)", "quality"),
    ("Plastering Inspection Checklist (قائمة فحص المحارة)", "quality"),
    ("Tiling Inspection Checklist (قائمة فحص البلاط)", "quality"),
    ("Painting Inspection Checklist (قائمة فحص الدهانات)", "quality"),
    ("Concrete Curing Record (سجل معالجة الخرسانة)", "quality"),
    ("Formwork Inspection Checklist (قائمة فحص الشدات)", "quality"),
    ("Reinforcement Inspection Checklist (قائمة فحص حديد التسليح)", "quality"),
    ("Post-Pour Inspection Report (تقرير الفحص بعد الصب)", "quality"),
    ("Pre-Pour Inspection Report (تقرير الفحص قبل الصب)", "quality"),
    ("Quality Observation Report (تقرير ملاحظات الجودة)", "quality"),
    ("Corrective Action Request (طلب إجراء تصحيحي)", "quality"),
    ("Preventive Action Request (طلب إجراء وقائي)", "quality"),
    ("Calibration Certificate Record (سجل شهادات المعايرة)", "quality"),
    ("Material Rejection Form (نموذج رفض مواد)", "quality"),
    ("Material Storage Inspection (فحص تخزين المواد)", "quality"),
    ("Sample Approval Form (نموذج اعتماد عينات)", "quality"),
    ("Mock-up Approval Form (نموذج اعتماد النموذج التجريبي)", "quality"),
    ("Quality Closeout Report (تقرير إغلاق الجودة)", "quality"),
    ("Final Quality Inspection Report (تقرير الفحص النهائي للجودة)", "quality"),
    ("Test Request Form (نموذج طلب اختبار)", "quality"),
    ("Concrete Mix Design Approval (اعتماد تصميم خلطة الخرسانة)", "quality"),
    ("Asphalt Mix Design Approval (اعتماد تصميم خلطة الأسفلت)", "quality"),
    ("Aggregate Gradation Report (تقرير التدرج الحبيبي للركام)", "quality"),
    ("Concrete Temperature Record (سجل درجة حرارة الخرسانة)", "quality"),
    ("Curing Compound Application Record (سجل تطبيق مركب المعالجة)", "quality"),
    ("Rebar Coupler Inspection Report (تقرير فحص وصلات الحديد الميكانيكية)", "quality"),
    ("Welding Inspection Report (تقرير فحص اللحام)", "quality"),
    ("Bolted Connection Inspection Report (تقرير فحص الوصلات المثبتة بمسامير)", "quality"),
    ("Steel Erection Inspection Checklist (قائمة فحص تركيب المنشآت الفولاذية)", "quality"),
    ("Pile Integrity Test Report (تقرير اختبار سلامة الخوازيق)", "quality"),
    ("Load Test Report (تقرير اختبار التحميل)", "quality"),
    ("Water Pressure Test Report (تقرير اختبار ضغط المياه)", "quality"),
    ("Duct Leakage Test Report (تقرير اختبار تسرب المجاري)", "quality"),
    ("Pipeline Bedding Inspection (فحص فرشة خطوط الأنابيب)", "quality"),
    ("Backfill Compaction Inspection (فحص دمك الردم)", "quality"),
    ("Manhole Inspection Checklist (قائمة فحص غرف التفتيش)", "quality"),
    ("Road Subgrade Inspection Checklist (قائمة فحص طبقة الأساس للطرق)", "quality"),
    ("Asphalt Paving Inspection Checklist (قائمة فحص رصف الأسفلت)", "quality"),
    ("Concrete Pavement Inspection Checklist (قائمة فحص الرصف الخرساني)", "quality"),
    ("Road Marking Inspection Report (تقرير فحص علامات الطرق)", "quality"),
    ("Geotextile Installation Inspection Report (تقرير فحص تركيب الجيوتكستايل)", "quality"),
    ("Survey Inspection Report (تقرير فحص المساحة)", "quality"),
    ("Setting Out Approval Form (نموذج اعتماد توقيع المحاور)", "quality"),
    ("As-Built Drawing Verification (التحقق من الرسومات التنفيذية)", "quality"),

    # =========================================================
    # SAFETY & HEALTH (سلامة)
    # =========================================================
    ("Safety Inspection Checklist (قائمة فحص السلامة)", "safety"),
    ("Toolbox Talk Record (سجل اجتماع السلامة)", "safety"),
    ("Permit to Work (تصريح عمل)", "safety"),
    ("Incident Report (تقرير حادث)", "safety"),
    ("Risk Assessment Form (نموذج تقييم مخاطر)", "safety"),
    ("PPE Compliance Record (سجل الالتزام بمعدات الوقاية)", "safety"),
    ("Emergency Evacuation Plan (خطة إخلاء طوارئ)", "safety"),
    ("Safety Observation Report (تقرير ملاحظات السلامة)", "safety"),
    ("Hot Work Permit (تصريح عمل ساخن)", "safety"),
    ("Confined Space Entry Permit (تصريح دخول الأماكن المغلقة)", "safety"),
    ("Excavation Permit (تصريح حفر)", "safety"),
    ("Lifting Plan Approval Form (نموذج اعتماد خطة الرفع)", "safety"),
    ("Crane Inspection Checklist (قائمة فحص الرافعة)", "safety"),
    ("Scaffolding Inspection Checklist (قائمة فحص السقالات)", "safety"),
    ("Fall Protection Inspection Checklist (قائمة فحص الحماية من السقوط)", "safety"),
    ("Site Safety Audit Report (تقرير مراجعة سلامة الموقع)", "safety"),
    ("Safety Training Record (سجل تدريب السلامة)", "safety"),
    ("Near Miss Report (تقرير حادث وشيك)", "safety"),
    ("First Aid Record (سجل الإسعافات الأولية)", "safety"),
    ("Fire Extinguisher Inspection Record (سجل فحص طفايات الحريق)", "safety"),
    ("Emergency Drill Report (تقرير تدريب الطوارئ)", "safety"),
    ("Site Safety Induction Form (نموذج تعريف السلامة للموقع)", "safety"),
    ("Safety Violation Report (تقرير مخالفة سلامة)", "safety"),
    ("Weekly Safety Report (تقرير السلامة الأسبوعي)", "safety"),
    ("Monthly Safety Report (تقرير السلامة الشهري)", "safety"),
    ("Occupational Health Record (سجل الصحة المهنية)", "safety"),
    ("Environmental Inspection Checklist (قائمة فحص البيئة)", "safety"),
    ("Waste Management Record (سجل إدارة المخلفات)", "safety"),
    ("Noise Monitoring Record (سجل رصد الضوضاء)", "safety"),
    ("Dust Monitoring Record (سجل رصد الأتربة)", "safety"),
    ("Site Housekeeping Inspection (فحص نظافة الموقع)", "safety"),
    ("Electrical Safety Inspection (فحص السلامة الكهربائية)", "safety"),
    ("Temporary Works Inspection (فحص الأعمال المؤقتة)", "safety"),
    ("Demolition Safety Checklist (قائمة فحص سلامة الهدم)", "safety"),
    ("Traffic Management Plan Checklist (قائمة فحص خطة إدارة المرور)", "safety"),
    ("Public Safety Checklist (قائمة فحص سلامة الجمهور)", "safety"),
    ("Safety Signage Inspection (فحص لافتات السلامة)", "safety"),
    ("Personal Protective Equipment Issue Record (سجل صرف معدات الوقاية الشخصية)", "safety"),
    ("Accident Investigation Report (تقرير التحقيق في الحادث)", "safety"),
    ("Safety Committee Meeting Minutes (محضر اجتماع لجنة السلامة)", "safety"),

    # =========================================================
    # TECHNICAL / SITE (فني)
    # =========================================================
    ("Site Inspection Report (محضر معاينة موقع)", "technical"),
    ("Soil Report Template (تقرير التربة)", "technical"),
    ("Setting Out Record (سجل توقيع المحاور)", "technical"),
    ("As-Built Drawing Record (سجل الرسومات التنفيذية)", "technical"),
    ("Shop Drawing Submittal (تقديم لوحات تفصيلية)", "technical"),
    ("Technical Query Form (استفسار فني)", "technical"),
    ("Site Measurement Sheet (ورقة قياسات موقع)", "technical"),
    ("Construction Progress Report (تقرير تقدم الأعمال)", "technical"),
    ("Bar Bending Schedule (جدول تقطيع الحديد)", "technical"),
    ("Concrete Pour Card (كارت صب الخرسانة)", "technical"),
    ("Formwork Design Calculation (حساب تصميم الشدات)", "technical"),
    ("Scaffolding Design Calculation (حساب تصميم السقالات)", "technical"),
    ("Excavation Support Design (تصميم دعم الحفر)", "technical"),
    ("Dewatering Design (تصميم نزح المياه)", "technical"),
    ("Pile Layout Drawing (رسم تخطيط الخوازيق)", "technical"),
    ("Foundation Layout Drawing (رسم تخطيط الأساسات)", "technical"),
    ("Column Layout Drawing (رسم تخطيط الأعمدة)", "technical"),
    ("Beam Layout Drawing (رسم تخطيط الكمرات)", "technical"),
    ("Slab Layout Drawing (رسم تخطيط البلاطات)", "technical"),
    ("Staircase Detail Drawing (رسم تفاصيل السلم)", "technical"),
    ("Reinforcement Detail Drawing (رسم تفاصيل التسليح)", "technical"),
    ("Structural Steel Detail Drawing (رسم تفاصيل المنشآت الفولاذية)", "technical"),
    ("Architectural Detail Drawing (رسم تفاصيل معماري)", "technical"),
    ("MEP Coordination Drawing (رسم تنسيق الأعمال الكهروميكانيكية)", "technical"),
    ("Waterproofing Detail Drawing (رسم تفاصيل العزل المائي)", "technical"),
    ("Thermal Insulation Detail Drawing (رسم تفاصيل العزل الحراري)", "technical"),
    ("Fire Fighting Layout Drawing (رسم تخطيط مكافحة الحريق)", "technical"),
    ("Plumbing Layout Drawing (رسم تخطيط السباكة)", "technical"),
    ("Electrical Layout Drawing (رسم تخطيط الكهرباء)", "technical"),
    ("HVAC Layout Drawing (رسم تخطيط التكييف)", "technical"),
    ("Elevator Installation Drawing (رسم تركيب المصعد)", "technical"),
    ("Survey Data Sheet (ورقة بيانات المساحة)", "technical"),
    ("Volume Calculation Sheet (ورقة حساب الكميات)", "technical"),
    ("Bill of Quantities (BOQ) - مقايسة الأعمال", "technical"),
    ("Quantity Take-off Sheet (ورقة حصر الكميات)", "technical"),
    ("Material Take-off Sheet (ورقة حصر المواد)", "technical"),
    ("Site Instructions Log (سجل تعليمات الموقع)", "technical"),
    ("Request for Inspection (طلب فحص)", "technical"),
    ("Work Completion Certificate (شهادة إتمام الأعمال)", "technical"),
    ("Handover Inspection Report (تقرير فحص التسليم)", "technical"),
    ("Punch List (قائمة الملاحظات)", "technical"),
    ("Snag List (قائمة العيوب)", "technical"),
    ("Defects Liability Report (تقرير فترة الضمان)", "technical"),
    ("Operation and Maintenance Manual (دليل التشغيل والصيانة)", "technical"),
    ("Spare Parts List (قائمة قطع الغيار)", "technical"),
    ("Commissioning Report (تقرير التشغيل التجريبي)", "technical"),
    ("Testing and Commissioning Plan (خطة الفحص والتشغيل التجريبي)", "technical"),
    ("Start-up Report (تقرير بدء التشغيل)", "technical"),
    ("Performance Test Report (تقرير اختبار الأداء)", "technical"),
    ("As-Built Drawing Register (سجل الرسومات التنفيذية)", "technical"),

    # =========================================================
    # FINANCIAL (مالي)
    # =========================================================
    ("Interim Payment Certificate (مستخلص أعمال)", "financial"),
    ("Purchase Order - PO (طلب شراء)", "financial"),
    ("Material Requisition Form (طلب صرف مواد)", "financial"),
    ("Labour Return Form (سجل عمالة يومي)", "financial"),
    ("Equipment Log (سجل معدات)", "financial"),
    ("Cost Variation Claim (مطالبة بتكلفة إضافية)", "financial"),
    ("Final Payment Certificate (مستخلص نهائي)", "financial"),
    ("Advance Payment Certificate (مستخلص دفعة مقدمة)", "financial"),
    ("Retention Release Certificate (شهادة الإفراج عن المحتجز)", "financial"),
    ("Bank Guarantee Form (نموذج ضمان بنكي)", "financial"),
    ("Performance Bond (ضمان أداء)", "financial"),
    ("Advance Payment Guarantee (ضمان دفعة مقدمة)", "financial"),
    ("Invoice Form (نموذج فاتورة)", "financial"),
    ("Payment Voucher (سند صرف)", "financial"),
    ("Receipt Voucher (سند قبض)", "financial"),
    ("Petty Cash Voucher (سند صرف نقدية)", "financial"),
    ("Cost Estimate Sheet (ورقة تقدير التكاليف)", "financial"),
    ("Budget Breakdown (تفصيل الميزانية)", "financial"),
    ("Cash Flow Statement (بيان التدفق النقدي)", "financial"),
    ("Cost Control Report (تقرير ضبط التكاليف)", "financial"),
    ("Earned Value Analysis Report (تقرير تحليل القيمة المكتسبة)", "financial"),
    ("Variation Order Pricing (تسعير أمر التغيير)", "financial"),
    ("Claim Submission Form (نموذج تقديم مطالبة)", "financial"),
    ("Claim Assessment Report (تقرير تقييم المطالبة)", "financial"),
    ("Daywork Sheet (ورقة عمل باليومية)", "financial"),
    ("Time Sheet (ورقة تسجيل الوقت)", "financial"),
    ("Overtime Authorization (تفويض العمل الإضافي)", "financial"),
    ("Subcontractor Payment Certificate (مستخلص مقاول باطن)", "financial"),
    ("Supplier Payment Certificate (مستخلص مورد)", "financial"),
    ("Material On-Site Report (تقرير المواد بالموقع)", "financial"),
    ("Waste and Loss Report (تقرير الهدر والخسائر)", "financial"),
    ("Equipment Utilization Report (تقرير استخدام المعدات)", "financial"),
    ("Equipment Downtime Report (تقرير توقف المعدات)", "financial"),
    ("Labour Productivity Report (تقرير إنتاجية العمالة)", "financial"),
    ("Cost Code Allocation Sheet (ورقة تخصيص كود التكلفة)", "financial"),
    ("Financial Closeout Report (تقرير الإغلاق المالي)", "financial"),
    ("Final Account Statement (بيان الحساب النهائي)", "financial"),

    # =========================================================
    # PERMITS & LEGAL (قانوني)
    # =========================================================
    ("Building Permit Application (طلب ترخيص بناء)", "legal"),
    ("Site Validity Certificate (شهادة صلاحية موقع)", "legal"),
    ("Construction Value Form (نموذج حساب قيمة الأعمال)", "legal"),
    ("Insurance Certificate (شهادة تأمين)", "legal"),
    ("Building Completion Certificate (شهادة إتمام بناء)", "legal"),
    ("Building Permit (رخصة بناء)", "legal"),
    ("Demolition Permit (رخصة هدم)", "legal"),
    ("Excavation Permit (تصريح حفر)", "legal"),
    ("Fence Permit (تصريح سياج)", "legal"),
    ("Occupancy Certificate (شهادة إشغال)", "legal"),
    ("Fire Safety Certificate (شهادة سلامة من الحريق)", "legal"),
    ("Health and Safety Certificate (شهادة السلامة والصحة المهنية)", "legal"),
    ("Environmental Clearance (موافقة بيئية)", "legal"),
    ("Utility Connection Approval (موافقة توصيل المرافق)", "legal"),
    ("Electricity Connection Approval (موافقة توصيل الكهرباء)", "legal"),
    ("Water Connection Approval (موافقة توصيل المياه)", "legal"),
    ("Gas Connection Approval (موافقة توصيل الغاز)", "legal"),
    ("Sewer Connection Approval (موافقة توصيل الصرف)", "legal"),
    ("Telecom Connection Approval (موافقة توصيل الاتصالات)", "legal"),
    ("Civil Defense Approval (موافقة الحماية المدنية)", "legal"),
    ("Aviation Authority Approval (موافقة الطيران المدني)", "legal"),
    ("Antiquities Authority Approval (موافقة الآثار)", "legal"),
    ("Agricultural Land Conversion Approval (موافقة تحويل الأراضي الزراعية)", "legal"),
    ("Road Works Permit (تصريح أعمال الطرق)", "legal"),
    ("Traffic Diversion Permit (تصريح تحويل المرور)", "legal"),
    ("Night Work Permit (تصريح العمل الليلي)", "legal"),
    ("Temporary Structure Permit (تصريح منشأ مؤقت)", "legal"),
    ("Hoarding Permit (تصريح سياج مؤقت)", "legal"),
    ("Scaffolding Permit (تصريح سقالات)", "legal"),
    ("Crane Permit (تصريح رافعة)", "legal"),
    ("Explosives Permit (تصريح تفجير)", "legal"),
    ("Water Discharge Permit (تصريح صرف المياه)", "legal"),
    ("Waste Disposal Permit (تصريح التخلص من المخلفات)", "legal"),
    ("Noise Variance Permit (تصريح استثناء الضوضاء)", "legal"),
    ("Heritage Impact Assessment (تقييم التأثير على التراث)", "legal"),
    ("Environmental Impact Assessment (تقييم التأثير البيئي)", "legal"),
    ("Traffic Impact Study (دراسة التأثير المروري)", "legal"),
    ("Soil Investigation Report (تقرير أبحاث التربة)", "legal"),
    ("Structural Stability Report (تقرير الثبات الإنشائي)", "legal"),
    ("Fire Strategy Report (تقرير استراتيجية الحريق)", "legal"),
    ("Accessibility Compliance Report (تقرير الامتثال لذوي الاحتياجات)", "legal"),

    # =========================================================
    # HANDOVER & CLOSEOUT (تسليم)
    # =========================================================
    ("Handover Checklist (قائمة التسليم)", "handover"),
    ("Warranty Certificate (شهادة ضمان)", "handover"),
    ("Defects Liability Record (سجل فترة الضمان)", "handover"),
    ("Operation and Maintenance Manual (دليل التشغيل والصيانة)", "handover"),
    ("As-Built Document Register (سجل المستندات النهائية)", "handover"),
    ("Handover Certificate (شهادة تسليم)", "handover"),
    ("Practical Completion Certificate (شهادة الإنجاز العملي)", "handover"),
    ("Taking Over Certificate (شهادة الاستلام)", "handover"),
    ("Final Acceptance Certificate (شهادة القبول النهائي)", "handover"),
    ("Handover Meeting Minutes (محضر اجتماع التسليم)", "handover"),
    ("Handover Inspection Report (تقرير فحص التسليم)", "handover"),
    ("Punch List Closeout (إغلاق قائمة الملاحظات)", "handover"),
    ("Snag List Closeout (إغلاق قائمة العيوب)", "handover"),
    ("Defects Rectification Report (تقرير إصلاح العيوب)", "handover"),
    ("Warranty Claim Form (نموذج مطالبة ضمان)", "handover"),
    ("Warranty Claim Assessment (تقييم مطالبة الضمان)", "handover"),
    ("Maintenance Schedule (جدول الصيانة)", "handover"),
    ("Preventive Maintenance Plan (خطة الصيانة الوقائية)", "handover"),
    ("Corrective Maintenance Record (سجل الصيانة التصحيحية)", "handover"),
    ("Spare Parts Inventory (جرد قطع الغيار)", "handover"),
    ("Training Record for Client (سجل تدريب العميل)", "handover"),
    ("Key Handover Form (نموذج تسليم المفاتيح)", "handover"),
    ("Asset Register (سجل الأصول)", "handover"),
    ("Equipment Handover Form (نموذج تسليم المعدات)", "handover"),
    ("Material Handover Form (نموذج تسليم المواد)", "handover"),
    ("Document Handover Form (نموذج تسليم المستندات)", "handover"),
    ("As-Built Drawing Handover (تسليم الرسومات التنفيذية)", "handover"),
    ("O&M Manual Handover (تسليم دليل التشغيل والصيانة)", "handover"),
    ("Spare Parts Handover (تسليم قطع الغيار)", "handover"),
    ("Training Handover (تسليم التدريب)", "handover"),
    ("Final Cleaning Report (تقرير التنظيف النهائي)", "handover"),
    ("Demobilization Plan (خطة إخلاء الموقع)", "handover"),
    ("Site Restoration Report (تقرير إعادة تأهيل الموقع)", "handover"),
    ("Final Survey Report (تقرير المساحة النهائي)", "handover"),
    ("Final Quality Report (تقرير الجودة النهائي)", "handover"),
    ("Final Safety Report (تقرير السلامة النهائي)", "handover"),
    ("Final Environmental Report (تقرير البيئة النهائي)", "handover"),
    ("Project Closeout Report (تقرير إغلاق المشروع)", "handover"),
    ("Lessons Learned Report (تقرير الدروس المستفادة)", "handover"),
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
