# report_builder.py
# v4: strips <br> from all output. PDF tables render as real tables.

import io
import re
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from reportlab.lib import colors

try:
    from arabic_font import register_reportlab_fonts
    _ARABIC_FONT = register_reportlab_fonts()
except Exception:
    _ARABIC_FONT = None

_PDF_FONT = _ARABIC_FONT or "Helvetica"
_PDF_BOLD = (_ARABIC_FONT + "-Bold") if _ARABIC_FONT else "Helvetica-Bold"

_BR_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)


def _kill_br(s: str) -> str:
    """Replace any <br> / <br/> / <BR> with a single space."""
    return _BR_RE.sub(" ", str(s or ""))


def _safe(s: Any) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _pdf_styles():
    s = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=s["Heading1"],
                        fontName=_PDF_BOLD, fontSize=18, leading=24,
                        spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=s["Heading2"],
                        fontName=_PDF_BOLD, fontSize=13, leading=18,
                        spaceBefore=12, spaceAfter=6,
                        textColor=colors.HexColor("#1a2342"))
    h3 = ParagraphStyle("h3", parent=s["Heading3"],
                        fontName=_PDF_BOLD, fontSize=11, leading=15,
                        spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("body", parent=s["BodyText"],
                          fontName=_PDF_FONT, fontSize=10, leading=14,
                          spaceAfter=4)
    li = ParagraphStyle("li", parent=body, leftIndent=14, bulletIndent=4)
    cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=12,
                          spaceAfter=0)
    cell_hdr = ParagraphStyle("cell_hdr", parent=cell,
                              fontName=_PDF_BOLD, textColor=colors.white)
    warn = ParagraphStyle("warn", parent=body, textColor=colors.red)
    ok = ParagraphStyle("ok", parent=body, textColor=colors.green)
    return {"h1": h1, "h2": h2, "h3": h3, "body": body, "li": li,
            "cell": cell, "cell_hdr": cell_hdr, "warn": warn, "ok": ok}


_TABLE_SEP_RE = re.compile(r"^[\s|:\-]+$")


def _is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") and s.endswith("|") and len(s) > 2


def _split_row(line: str):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _parse_md_blocks(text: str):
    if not text:
        return
    lines = _kill_br(text).replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        if _is_table_row(line):
            rows = []
            while i < len(lines) and _is_table_row(lines[i]):
                rows.append(_split_row(lines[i]))
                i += 1
            clean = []
            for r in rows:
                if all(_TABLE_SEP_RE.match(c) or c == "" for c in r):
                    continue
                clean.append(r)
            if clean:
                width = max(len(r) for r in clean)
                clean = [r + [""] * (width - len(r)) for r in clean]
                yield ("table", clean)
            continue

        if line.startswith("### "):
            yield ("h3", line[4:].strip()); i += 1; continue
        if line.startswith("## "):
            yield ("h2", line[3:].strip()); i += 1; continue
        if line.startswith("# "):
            yield ("h1", line[2:].strip()); i += 1; continue
        if line.strip() in ("---", "***", "___"):
            yield ("hr", None); i += 1; continue

        if re.match(r"^\s*[-*]\s+", line):
            items = []
            while i < len(lines):
                m = re.match(r"^\s*[-*]\s+(.*)$", lines[i])
                if not m:
                    break
                items.append(m.group(1).rstrip())
                i += 1
            yield ("ul", items)
            continue

        if re.match(r"^\s*\d+[.)]\s+", line):
            items = []
            while i < len(lines):
                m = re.match(r"^\s*\d+[.)]\s+(.*)$", lines[i])
                if not m:
                    break
                items.append(m.group(1).rstrip())
                i += 1
            yield ("ol", items)
            continue

        para = [line.strip()]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                break
            if (nxt.startswith("#") or _is_table_row(nxt)
                    or re.match(r"^\s*[-*]\s+", nxt)
                    or re.match(r"^\s*\d+[.)]\s+", nxt)
                    or nxt.strip() in ("---", "***", "___")):
                break
            para.append(nxt.strip())
            i += 1
        yield ("p", " ".join(para))


def _inline_to_html(s: str) -> str:
    s = _kill_br(s)
    s = _safe(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
    s = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", s)
    return s


def _shape_pdf(s):
    if _ARABIC_FONT:
        try:
            from arabic_font import shape_arabic
            return shape_arabic(s)
        except Exception:
            return s
    return s


def _P_pdf(text, style):
    shaped = _shape_pdf(_kill_br(str(text or "")))
    return Paragraph(_inline_to_html(shaped), style)


def _strip_md(s: str) -> str:
    s = _kill_br(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`(.+?)`", r"\1", s)
    return s


def _blocks_to_txt(blocks):
    out = []
    for kind, payload in blocks:
        if kind == "h1":
            out.append(f"\n{'=' * 60}\n{payload}\n{'=' * 60}\n")
        elif kind == "h2":
            out.append(f"\n{'-' * 60}\n{payload}\n{'-' * 60}")
        elif kind == "h3":
            out.append(f"\n{payload}")
        elif kind == "p":
            out.append(_strip_md(payload))
        elif kind == "ul":
            for it in payload:
                out.append(f"  - {_strip_md(it)}")
        elif kind == "ol":
            for n, it in enumerate(payload, 1):
                out.append(f"  {n}. {_strip_md(it)}")
        elif kind == "table":
            for r in payload:
                out.append("  " + " | ".join(_strip_md(c) for c in r))
        elif kind == "hr":
            out.append("-" * 40)
    return "\n".join(out)


def _blocks_to_pdf(blocks, styles):
    flow = []
    for kind, payload in blocks:
        if kind == "h1":
            flow.append(_P_pdf(payload, styles["h1"]))
        elif kind == "h2":
            flow.append(_P_pdf(payload, styles["h2"]))
        elif kind == "h3":
            flow.append(_P_pdf(payload, styles["h3"]))
        elif kind == "p":
            flow.append(_P_pdf(payload, styles["body"]))
        elif kind == "ul":
            for it in payload:
                flow.append(_P_pdf("•  " + it, styles["li"]))
        elif kind == "ol":
            for n, it in enumerate(payload, 1):
                flow.append(_P_pdf(f"{n}.  {it}", styles["li"]))
        elif kind == "hr":
            flow.append(Spacer(1, 6))
        elif kind == "table":
            ncol = len(payload[0]) if payload else 0
            if not ncol:
                continue
            avail = 17 * cm
            col_w = [avail / ncol] * ncol
            data = []
            for ridx, row in enumerate(payload):
                row_cells = []
                for c in row:
                    style = (styles["cell_hdr"] if ridx == 0
                             else styles["cell"])
                    row_cells.append(_P_pdf(c, style))
                data.append(row_cells)
            t = Table(data, colWidths=col_w, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0),
                 colors.HexColor("#1a2342")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1),
                 [colors.white, colors.HexColor("#f3f5fa")]),
            ]))
            flow.append(Spacer(1, 4))
            flow.append(t)
            flow.append(Spacer(1, 6))
    return flow


def _blocks_to_docx(blocks, doc):
    from docx.shared import RGBColor
    for kind, payload in blocks:
        if kind == "h1":
            doc.add_heading(_strip_md(payload), level=0)
        elif kind == "h2":
            h = doc.add_heading(_strip_md(payload), level=1)
            for r in h.runs:
                r.font.color.rgb = RGBColor(0x1a, 0x23, 0x42)
        elif kind == "h3":
            doc.add_heading(_strip_md(payload), level=2)
        elif kind == "p":
            doc.add_paragraph(_strip_md(payload))
        elif kind == "ul":
            for it in payload:
                doc.add_paragraph(_strip_md(it), style="List Bullet")
        elif kind == "ol":
            for it in payload:
                doc.add_paragraph(_strip_md(it), style="List Number")
        elif kind == "hr":
            doc.add_paragraph("")
        elif kind == "table":
            n_rows = len(payload)
            n_cols = len(payload[0]) if payload else 0
            if not n_rows or not n_cols:
                continue
            tbl = doc.add_table(rows=n_rows, cols=n_cols)
            tbl.style = "Light Grid Accent 1"
            for r_idx, row in enumerate(payload):
                for c_idx, cell in enumerate(row):
                    c = tbl.cell(r_idx, c_idx)
                    c.text = _strip_md(cell)
                    if r_idx == 0:
                        for para in c.paragraphs:
                            for run in para.runs:
                                run.bold = True
            doc.add_paragraph("")


def build_txt(filename: str, result: dict) -> bytes:
    lines = [f"HUBx Report - {filename}", "=" * 60,
             f"Score: {result.get('score', 0.0)}", "",
             "Summary:", _kill_br(result.get("summary", "")), ""]
    issues = result.get("issues", []) or []
    lines.append(f"Issues found: {len(issues)}")
    lines.append("-" * 60)
    for i, issue in enumerate(issues, 1):
        lines.append(f"\n[{i}] {issue.get('severity', '').upper()}")
        lines.append(f"Location:  {_kill_br(issue.get('location', ''))}")
        lines.append(f"Problem:   {_kill_br(issue.get('problem', ''))}")
        lines.append(f"Fix:       {_kill_br(issue.get('fix', ''))}")
        lines.append(f"Reference: {_kill_br(issue.get('reference', ''))}")
    return "\n".join(lines).encode("utf-8")


def build_pdf(filename: str, result: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    styles = _pdf_styles()
    story = [Paragraph("HUBx Engineering Review", styles["h1"]),
             _P_pdf(f"File: {filename}", styles["body"])]
    score = float(result.get("score", 0.0))
    story.append(Paragraph(
        f"Score: <b>{score:.2f}</b> / 1.00",
        styles["ok"] if score >= 0.7 else styles["warn"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Summary", styles["h2"]))
    story.append(_P_pdf(result.get("summary", ""), styles["body"]))
    story.append(Spacer(1, 0.3 * cm))
    issues = result.get("issues", []) or []
    story.append(Paragraph(f"Issues ({len(issues)})", styles["h2"]))
    if issues:
        data = [["#", "Severity", "Location", "Problem", "Fix", "Reference"]]
        for i, issue in enumerate(issues, 1):
            data.append([str(i),
                         _P_pdf(issue.get("severity", ""), styles["cell"]),
                         _P_pdf(issue.get("location", ""), styles["cell"]),
                         _P_pdf(issue.get("problem", ""), styles["cell"]),
                         _P_pdf(issue.get("fix", ""), styles["cell"]),
                         _P_pdf(issue.get("reference", ""), styles["cell"])])
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
        story.append(Paragraph("No issues detected.", styles["body"]))
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
    ws.append(["Summary", _kill_br(result.get("summary", ""))])
    ws2 = wb.create_sheet("Issues")
    ws2.append(["#", "Severity", "Location", "Problem", "Fix", "Reference"])
    for i, issue in enumerate(result.get("issues", []) or [], 1):
        ws2.append([i,
                    _kill_br(issue.get("severity", "")),
                    _kill_br(issue.get("location", "")),
                    _kill_br(issue.get("problem", "")),
                    _kill_br(issue.get("fix", "")),
                    _kill_br(issue.get("reference", ""))])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def topic_pdf(title: str, category: str, version: int,
              body: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    styles = _pdf_styles()
    story = [_P_pdf(title, styles["h1"]),
             _P_pdf(f"Category: {category}   |   Version: v{version}",
                    styles["body"]),
             Spacer(1, 0.3 * cm)]
    blocks = list(_parse_md_blocks(body or ""))
    story.extend(_blocks_to_pdf(blocks, styles))
    doc.build(story)
    return buf.getvalue()


def topic_txt(title: str, category: str, version: int,
              body: str) -> bytes:
    head = (f"{title}\n"
            f"Category: {category}  |  Version: v{version}\n"
            + "=" * 60 + "\n")
    blocks = list(_parse_md_blocks(body or ""))
    return (head + _blocks_to_txt(blocks)).encode("utf-8")


def topic_docx(title: str, category: str, version: int,
               body: str) -> bytes:
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.add_heading(title, level=0)
    p = doc.add_paragraph(f"Category: {category}  |  Version: v{version}")
    p.runs[0].font.size = Pt(10)
    blocks = list(_parse_md_blocks(body or ""))
    _blocks_to_docx(blocks, doc)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
