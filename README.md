# HUBx v2 — Civil Quality Engineering Self-Learning Tool

A self-learning assistant for Egyptian civil quality engineers.

## What it does

1. **Self-learning loop (every 20s)**: asks Gemini about civil quality
   topics from `sources.py`, stores the answer in Turso, then every other
   cycle refines the oldest note — so the knowledge base gets sharper over
   time without retraining any model.
2. **Document review**: upload a PDF, TXT, XLSX, PNG or JPG. The app
   extracts the text (OCR for images via Gemini vision), then asks Gemini
   to find every engineering mistake against Egyptian codes (ECP 203,
   205, 202, ESS). Results come back as a scored issue list with fixes and
   references.
3. **Download reports**: TXT, PDF (reportlab), XLSX (openpyxl).
4. **Knowledge browser**: read every self-learned note, filtered by
   category.

## Stack

- Python 3.11+
- NiceGUI
- Turso (libsql)
- Gemini API (`gemini-3.5-flash-lite`)
- PyMuPDF (PDF text), openpyxl (Excel), reportlab (PDF output),
  Pillow + Gemini vision (image OCR)
- Render (free tier compatible)

## Setup

### 1. Turso
```bash
curl -sSfL https://get.tur.so/install.sh | bash
turso auth signup
turso db create hubx
turso db show hubx --url
turso db tokens create hubx
