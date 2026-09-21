# file_reader.py
# Extract plain text from uploaded files.
# - PDF: PyMuPDF (works for text-layer PDFs, no OCR)
# - XLSX: openpyxl
# - TXT: plain read
# - Images (png/jpg): Gemini vision OCR (fallback: return "")

import os
import logging

logger = logging.getLogger(__name__)


def read_txt(path: str) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except Exception:
            continue
    return ""


def read_pdf(path: str) -> str:
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        parts = []
        for page in doc:
            parts.append(page.get_text("text"))
        doc.close()
        return "\n".join(parts)
    except Exception as e:
        logger.error("PDF read failed: %s", e)
        return ""


def read_xlsx(path: str) -> str:
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


async def read_image(path: str) -> str:
    from gemini import ocr_image
    return await ocr_image(path)


async def extract_text(path: str, filename: str) -> tuple[str, str]:
    """
    Returns (text, file_type). file_type is a short label.
    Chooses extractor based on extension.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return read_pdf(path), "pdf"
    if ext == ".txt":
        return read_txt(path), "txt"
    if ext in (".xlsx", ".xlsm", ".xls"):
        if ext == ".xls":
            # openpyxl doesn't read legacy .xls; return empty with note.
            return "", "xls-unsupported"
        return read_xlsx(path), "xlsx"
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".bmp"):
        return await read_image(path), "image"
    return "", "unknown"
