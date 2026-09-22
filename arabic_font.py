# arabic_font.py
# Downloads an Arabic-capable TTF once, registers it with reportlab,
# and exposes @font-face CSS for WeasyPrint. Safe to import anywhere.

import os
import logging
import urllib.request

logger = logging.getLogger(__name__)

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
os.makedirs(FONT_DIR, exist_ok=True)

AMIRI_REGULAR = os.path.join(FONT_DIR, "Amiri-Regular.ttf")
AMIRI_BOLD = os.path.join(FONT_DIR, "Amiri-Bold.ttf")

_FONT_SOURCES = [
    (AMIRI_REGULAR,
     "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Regular.ttf"),
    (AMIRI_BOLD,
     "https://raw.githubusercontent.com/google/fonts/main/ofl/amiri/Amiri-Bold.ttf"),
]

_registered = False


def _download(path, url):
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return True
    try:
        logger.info("Downloading font: %s", url)
        req = urllib.request.Request(url, headers={"User-Agent": "HUBx/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return os.path.getsize(path) > 10000
    except Exception as e:
        logger.warning("Font download failed (%s): %s", url, e)
        return False


def ensure_fonts():
    ok = True
    for path, url in _FONT_SOURCES:
        if not _download(path, url):
            ok = False
    return ok


def register_reportlab_fonts():
    """Register Amiri with reportlab once. Returns 'Amiri' or None."""
    global _registered
    if _registered:
        return "Amiri"
    if not ensure_fonts():
        return None
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        pdfmetrics.registerFont(TTFont("Amiri", AMIRI_REGULAR))
        pdfmetrics.registerFont(TTFont("Amiri-Bold", AMIRI_BOLD))
        registerFontFamily("Amiri", normal="Amiri", bold="Amiri-Bold",
                           italic="Amiri", boldItalic="Amiri-Bold")
        _registered = True
        return "Amiri"
    except Exception as e:
        logger.warning("reportlab font registration failed: %s", e)
        return None


def has_arabic(s):
    if not s:
        return False
    for c in s:
        o = ord(c)
        if (0x0600 <= o <= 0x06FF or 0x0750 <= o <= 0x077F
                or 0xFB50 <= o <= 0xFDFF or 0xFE70 <= o <= 0xFEFF):
            return True
    return False


def shape_arabic(s):
    """Reshape + bidi-reorder for reportlab rendering."""
    if not s or not has_arabic(s):
        return s
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(s)))
    except Exception as e:
        logger.warning("arabic reshape failed: %s", e)
        return s


def css_for_weasyprint():
    """Return @font-face CSS pointing at local Amiri files."""
    if not ensure_fonts():
        return ""
    reg = "file://" + AMIRI_REGULAR
    bold = "file://" + AMIRI_BOLD
    return (
        "@font-face { font-family: 'Amiri'; "
        f"src: url('{reg}') format('truetype'); font-weight: normal; }}"
        "@font-face { font-family: 'Amiri'; "
        f"src: url('{bold}') format('truetype'); font-weight: bold; }}"
    )
