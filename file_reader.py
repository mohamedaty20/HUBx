# file_reader.py
# Extract plain text from uploaded files.

import os
import logging

logger = logging.getLogger(__name__)


def read_txt(path):
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ""


def read_pdf(path):
    try:
        import fitz
        doc = fitz.open(path)
        parts = [page.get_text("text") for page in doc]
        doc.close()
        return "\n".join(parts)
    except Exception as e:
        logger.error("PDF read failed: %s", e)
        return ""


def read_xlsx(path):
    try:
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True, read_only=True)
        parts = []
        for sheet in wb.sheetnames:
            ws = wb[sheet]
            parts.append(f"# Sheet: {sheet}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(cells):
                    parts.append(" | ".join(cells))
        wb.close()
        return "\n".join(parts)
    except Exception as e:
        logger.error("XLSX read failed: %s", e)
        return ""


async def read_image(path):
    from gemini import ocr_image
    return await ocr_image(path)


async def extract_text(path, filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return read_pdf(path), "pdf"
    if ext == ".txt":
        return read_txt(path), "txt"
    if ext in (".xlsx", ".xlsm"):
        return read_xlsx(path), "xlsx"
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return await read_image(path), "image"
    if ext == ".docx":
        try:
            from docx import Document
            d = Document(path)
            return "\n".join(p.text for p in d.paragraphs), "docx"
        except Exception:
            return "", "docx"
    return "", "unknown"
