# templates.py
from datetime import date
from state import STATE

PAPER_CSS = """
@page { size: A4; margin: 20mm 18mm 22mm 18mm; }
* { box-sizing: border-box; }
body { font-family: 'Cairo', 'Amiri', 'Noto Naskh Arabic', sans-serif;
       font-size: 12pt; color: #111; line-height: 1.6; }

.cover { text-align: center; padding-top: 40mm; }
.cover .org { font-size: 14pt; font-weight: 600; letter-spacing: .5px; }
.cover .faculty { font-size: 12pt; margin-top: 4mm; color:#333; }
.cover .rule { height: 2px; background: #111; margin: 8mm auto; width: 60%; }
.cover .ptitle { font-size: 22pt; font-weight: 700; margin: 10mm 0; }
.cover .subtitle { font-size: 13pt; color:#444; margin-bottom: 12mm; }

.meta { width: 100%; margin-top: 20mm; border-collapse: collapse; }
.meta td { padding: 3mm 2mm; font-size: 12pt; vertical-align: top; }
.meta .lbl { width: 35%; font-weight: 600; color:#222; }
.meta .val { width: 65%; border-bottom: 1px dotted #999; }

.section { margin-top: 12mm; }
.section h2 { font-size: 14pt; border-bottom: 1.5px solid #111;
              padding-bottom: 2mm; margin-bottom: 4mm; }
.section .body { text-align: justify; }

.fields { margin-top: 6mm; }
.fields .row { display: flex; margin-bottom: 4mm; }
.fields .row .k { width: 32%; font-weight: 600; }
.fields .row .v { width: 68%; border-bottom: 1px dotted #999; min-height: 6mm; }

.rtl { direction: rtl; text-align: right; }
.footer { position: fixed; bottom: 8mm; left: 0; right: 0;
          text-align: center; font-size: 9pt; color:#666; }
"""

def render_paper_html(job: dict, body_text: str) -> str:
    rtl = STATE.lang == "ar"
    cls = "rtl" if rtl else ""
    lang = "ar" if rtl else "en"
    d = date.today().isoformat()
    return f"""<!doctype html>
<html lang="{lang}" dir="{'rtl' if rtl else 'ltr'}">
<head><meta charset="utf-8"><style>{PAPER_CSS}</style></head>
<body class="{cls}">

  <div class="cover">
    <div class="org">{job.get('company','—')}</div>
    <div class="faculty">{job.get('location','Egypt')}</div>
    <div class="rule"></div>
    <div class="ptitle">{job.get('title','—')}</div>
    <div class="subtitle">{job.get('subtitle','Civil Engineering Project')}</div>
  </div>

  <table class="meta">
    <tr><td class="lbl">Project Name</td><td class="val">{job.get('title','')}</td></tr>
    <tr><td class="lbl">Engineer</td>   <td class="val">{job.get('recruiter_name','') or job.get('engineer','')}</td></tr>
    <tr><td class="lbl">Supervisor</td> <td class="val">{job.get('supervisor','')}</td></tr>
    <tr><td class="lbl">Company</td>    <td class="val">{job.get('company','')}</td></tr>
    <tr><td class="lbl">Location</td>   <td class="val">{job.get('location','')}</td></tr>
    <tr><td class="lbl">Date</td>       <td class="val">{d}</td></tr>
  </table>

  <div class="section">
    <h2>Description</h2>
    <div class="body">{body_text}</div>
  </div>

  <div class="footer">{job.get('url','')}</div>
</body></html>"""
