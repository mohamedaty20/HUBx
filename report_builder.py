# report_builder.py
# Build downloadable reports: TXT, PDF, DOCX.

import io
import json
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.lib import colors


def _safe(s: Any) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


# ---------------- check report ----------------

def build_txt(filename: str, result: dict) -> bytes:
    lines = [f"HUBx Report - {filename}", "=" * 60,
             f"Score: {result.get('score', 0.0)}", "",
             "Summary:", result.get("summary", ""), ""]
    issues = result.get("issues", []) or []
    lines.append(f"Issues found: {len(issues)}")
    lines.append("-" * 60)
    for i, issue in enumerate(issues, 1):
        lines.append(f"\n[{i}] {issue.get('severity', '').upper()}")
        lines.append(f"Location:  {issue.get('location', '')}")
        lines.append(f"Problem:   {issue.get('problem', '')}")
        lines.append(f"Fix:       {issue.get('fix', '')}")
        lines.append(f"Reference: {issue.get('reference', '')}")
    return "\n".join(lines).encode("utf-8")


def build_pdf(filename: str, result: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body = styles["BodyText"]
    warn = ParagraphStyle("warn", parent=body, textColor=colors.red)
    ok = ParagraphStyle("ok", parent=body, textColor=colors.green)

    story = [Paragraph("HUBx Engineering Review", h1),
             Paragraph(f"File: {_safe(filename)}", body)]
    score = float(result.get("score", 0.0))
    story.append(Paragraph(
        f"Score: <b>{score:.2f}</b> / 1.00",
        ok if score >= 0.7 else warn))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Summary", h2))
    story.append(Paragraph(_safe(result.get("summary", "")), body))
    story.append(Spacer(1, 0.4 * cm))
    issues = result.get("issues", []) or []
    story.append(Paragraph(f"Issues ({len(issues)})", h2))
    if issues:
        data = [["#", "Severity", "Location", "Problem", "Fix", "Reference"]]
        for i, issue in enumerate(issues, 1):
            data.append([str(i),
                         _safe(issue.get("severity", "")),
                         Paragraph(_safe(issue.get("location", "")), body),
                         Paragraph(_safe(issue.get("problem", "")), body),
                         Paragraph(_safe(issue.get("fix", "")), body),
                         Paragraph(_safe(issue.get("reference", "")), body)])
        tbl = Table(data, colWidths=[0.8 * cm, 1.8 * cm, 3 * cm,
                                     4.5 * cm, 4.5 * cm, 2.6 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No issues detected.", body))
    doc.build(story)
    return buf.getvalue()


def build_xlsx(filename: str, result: dict) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Field", "Value"])
    ws.append(["File", filename])
    ws.append(["Score", result.get("score", 0.0)])
    ws.append(["Summary", result.get("summary", "")])
    ws2 = wb.create_sheet("Issues")
    ws2.append(["#", "Severity", "Location", "Problem", "Fix", "Reference"])
    for i, issue in enumerate(result.get("issues", []) or [], 1):
        ws2.append([i,
                    issue.get("severity", ""),
                    issue.get("location", ""),
                    issue.get("problem", ""),
                    issue.get("fix", ""),
                    issue.get("reference", "")])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------- topic / template download ----------------

def _md_to_plain(md: str) -> str:
    """Very light markdown stripping for text/pdf/docx export."""
    if not md:
        return ""
    lines = []
    for line in md.split("\n"):
        s = line
        if s.startswith("### "):
            s = s[4:]
        elif s.startswith("## "):
            s = s[3:]
        elif s.startswith("# "):
            s = s[2:]
        s = s.replace("**", "").replace("*", "")
        lines.append(s)
    return "\n".join(lines)


def topic_pdf(title: str, category: str, version: int,
              body: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h2 = styles["Heading2"]
    body_s = styles["BodyText"]
    story = [Paragraph(_safe(title), h1),
             Paragraph(f"Category: {_safe(category)}  |  "
                       f"Version: v{version}", body_s),
             Spacer(1, 0.3 * cm)]
    for para in _md_to_plain(body).split("\n\n"):
        if not para.strip():
            continue
        first = para.strip().split("\n")[0]
        if first.isupper() and len(first) < 80:
            story.append(Paragraph(_safe(first), h2))
            rest = "\n".join(para.strip().split("\n")[1:])
            if rest.strip():
                story.append(Paragraph(_safe(rest), body_s))
        else:
            story.append(Paragraph(_safe(para.strip()), body_s))
        story.append(Spacer(1, 0.15 * cm))
    doc.build(story)
    return buf.getvalue()


def topic_txt(title: str, category: str, version: int,
              body: str) -> bytes:
    out = (f"{title}\n"
           f"Category: {category}  |  Version: v{version}\n"
           + "=" * 60 + "\n\n"
           + _md_to_plain(body))
    return out.encode("utf-8")


def topic_docx(title: str, category: str, version: int,
               body: str) -> bytes:
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.add_heading(title, level=0)
    p = doc.add_paragraph(f"Category: {category}  |  Version: v{version}")
    p.runs[0].font.size = Pt(10)
    for para in _md_to_plain(body).split("\n\n"):
        if not para.strip():
            continue
        lines = para.strip().split("\n")
        first = lines[0]
        if first.isupper() and len(first) < 80:
            doc.add_heading(first, level=2)
            rest = "\n".join(lines[1:])
            if rest.strip():
                doc.add_paragraph(rest)
        else:
            doc.add_paragraph(para.strip())
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
