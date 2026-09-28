# prices_sources.py
# Seed list of Egyptian construction-material price sources.
# kind is informational only (we use plain httpx for everything).

SEED_PRICE_SOURCES = [
    ("CAPMAS", "https://www.capmas.gov.eg", "html"),
    ("Aleqaria", "https://www.aleqaria.com.eg", "html"),
    ("Al Mal News", "https://www.almalnews.com", "html"),
    ("Amwal Al Ghad", "https://amwalalghad.com", "html"),
    ("Enterprise Egypt", "https://enterprise.news", "html"),
    ("Ezz Steel", "https://www.ezzsteel.com", "html"),
    ("Beshay Steel", "https://www.beshaysteel.com", "html"),
    ("Suez Steel", "https://www.suezsteel.com", "html"),
    ("Suez Cement", "https://www.suezcement.com.eg", "html"),
    ("Lafarge Egypt", "https://www.lafarge.com.eg", "html"),
    ("Cemex Egypt", "https://www.cemex.com.eg", "html"),
    ("Sinai Cement", "https://www.sinaicement.com", "html"),
    ("Misr Beni Suef Cement", "https://www.misrbenisuefcement.com", "html"),
    ("Egyptian Contractors Association", "https://www.eca.org.eg", "html"),
    ("Federation of Egyptian Industries", "https://www.fei.org.eg", "html"),
    ("Central Bank of Egypt", "https://www.cbe.org.eg", "html"),
    ("Daily News Egypt", "https://www.dailynewsegypt.com", "html"),
    ("Zawya Egypt", "https://www.zawya.com/en", "html"),
    ("Ahram Online Business", "https://english.ahram.org.eg", "html"),
    ("SteelOrbis Egypt", "https://www.steelorbis.com/steel-news/egypt/", "html"),
    ("Global Cement", "https://www.globalcement.com", "html"),
    ("World Cement", "https://www.worldcement.com", "html"),
    ("Egypt Independent", "https://www.egyptindependent.com", "html"),
    ("Trading Economics Egypt", "https://tradingeconomics.com/egypt", "html"),
]
