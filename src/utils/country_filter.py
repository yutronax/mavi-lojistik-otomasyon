# -*- coding: utf-8 -*-
import difflib
import re

# Comprehensive list of countries (in Turkish and English)
# Excluding Turkey
COUNTRIES = [
    # Neighboring & common
    "ALMANYA", "AVUSTURYA", "BELÇİKA", "BULGARİSTAN", "ÇEK CUMHURİYETİ", "DANİMARKA", 
    "ESTONYA", "FİNLANDİYA", "FRANSA", "HIRVATİSTAN", "HOLLANDA", "İNGİLTERE", "İRLANDA", 
    "İSPANYA", "İSVEÇ", "İTALYA", "LETONYA", "LİTVANYA", "LÜKSEMBURG", "MACARİSTAN", 
    "MALTA", "POLONYA", "PORTEKİZ", "ROMANYA", "SLOVAKYA", "SLOVENYA", "YUNANİSTAN",
    "RUSYA", "UKRAYNA", "AZERBAYCAN", "GÜRCİSTAN", "ERMENİSTAN", "IRAK", "İRAN", "SURİYE",
    "LÜBNAN", "ÜRDÜN", "İSRAİL", "MISIR", "LİBYA", "TUNUS", "CEZAYİR", "FAS",
    "ABD", "AMERİKA", "KANADA", "MEKSİKA", "BREZİLYA", "ARJANTİN", "ÇİN", "JAPONYA", 
    "GÜNEY KORE", "HİNDİSTAN", "PAKİSTAN", "AFGANİSTAN", "ÖZBEKİSTAN", "KAZAKİSTAN",
    "TÜRKMENİSTAN", "KIRGIZİSTAN", "SIRBİSTAN", "KARADAĞ", "ARNAVUTLUK", "MAKEDONYA",
    "BOSNA HERSEK", "İSVİÇRE", "NORVEÇ", "İZLANDA", "DUBAİ", "KATAR", "KUVEYT", 
    "SUUDİ ARABİSTAN", "BİRLEŞİK ARAP EMİRLİKLERİ"
]

def _deaccent(text: str) -> str:
    """Removes Turkish accents and converts to English-friendly uppercase."""
    if not text: return ""
    # Standardize to common uppercase letters
    rep = {
        'ı': 'I', 'i': 'I', 'ğ': 'G', 'ü': 'U', 'ş': 'S', 'ö': 'O', 'ç': 'C',
        'İ': 'I', 'Ğ': 'G', 'Ü': 'U', 'Ş': 'S', 'Ö': 'O', 'Ç': 'C', 'I': 'I'
    }
    res = ""
    for char in text:
        res += rep.get(char, char.upper())
    return res

def is_foreign_country_message(text: str, threshold: float = 0.9) -> bool:
    """
    Checks if the text contains a foreign country name with high similarity.
    """
    if not text:
        return False
        
    # Normalize message text to base characters
    norm_text = _deaccent(text)
    
    # Pre-processed countries list
    normalized_countries = [_deaccent(c) for c in COUNTRIES]
    
    # 1. Full Text Substring Check (Fast)
    for country in normalized_countries:
        if country in norm_text:
            return True
            
    # 2. Fuzzy Match on words
    words = re.findall(r'[A-Z]+', norm_text)
    for word in words:
        if len(word) < 4: continue # Skip very short words (but keeping USA/ABD logic via substring above)
        
        matches = difflib.get_close_matches(word, normalized_countries, n=1, cutoff=threshold)
        if matches:
            return True
            
    return False

def has_cyrillic(text: str) -> bool:
    """
    Checks if the text contains any Cyrillic (Russian, etc.) characters.
    """
    if not text:
        return False
    # Cyrillic range: \u0400-\u04FF
    return bool(re.search(r'[\u0400-\u04FF]', text))
