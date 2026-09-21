# pdf_export.py
import os, pathlib
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

FONT_DIR = pathlib.Path(__file__).parent / "fonts"
FONT_DIR.mkdir(exist_ok=True)

# Download Cairo-Regular.ttf and Cairo-Bold.ttf once and drop them in ./fonts/
# https://fonts.google.com/specimen/Cairo
FONT_CSS = CSS(string=f"""
@font-face {{ font-family:'Cairo'; font-weight:400;
  src: url('file://{FONT_DIR}/Cairo-Regular.ttf'); }}
@font-face {{ font-family:'Cairo'; font-weight:700;
  src: url('file://{FONT_DIR}/Cairo-Bold.ttf'); }}
""")

def html_to_pdf(html_str: str, out_path: str) -> str:
    fc = FontConfiguration()
    HTML(string=html_str, base_url=str(FONT_DIR)).write_pdf(
        out_path, stylesheets=[FONT_CSS], font_config=fc
    )
    return out_path
