import re

def _extract_price_regex(text: str) -> str:
    if not text: return "SORUNUZ"
    clean_text = text.upper().replace('İ', 'I').replace('₺', ' TL ')
    pattern = r'(?<!\d)(?!(?:1360|860)(?!\d))(\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{1,2})?|\d+)(?!\d)'
    
    matches = list(re.finditer(pattern, clean_text))
    candidates = []
    for m in matches:
        val_str = m.group(1)
        digits = re.sub(r'\D', '', val_str)
        val_norm = val_str.replace(',', '.')
        if val_norm in ['13.60', '1360', '860']: continue
        # 2. CRITICAL: Exclude Phone Numbers
        if len(digits) >= 10 and (digits.startswith('05') or digits.startswith('5')):
            continue
        if (len(digits) in [3, 4]) and (digits.startswith('05') or digits.startswith('5')):
            after = clean_text[m.end():m.end()+10]
            if re.search(r'\d', after):
                continue
        
        has_separator = '.' in val_str or ',' in val_str
        surrounding = clean_text[max(0, m.start()-15):min(len(clean_text), m.end()+15)]
        has_keyword = any(kw in surrounding for kw in ['TL', 'KDV', 'FIYAT', 'HESAP', 'DAHIL', 'GIRIS', 'CORDER'])
        
        if not (has_separator or has_keyword): continue
        
        score = 0
        if has_keyword: score += 10
        if has_separator: score += 5
        candidates.append((val_str, score, m.start()))
        
    if not candidates: return "SORUNUZ"
    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    return candidates[0][0]

tests = [
    ("15000", "SORUNUZ"),
    ("15.000", "15.000"),
    ("450+KDV", "450"),
    ("450 TL", "450"),
    ("Fiyat 12000", "12000"),
    ("13.60 dorseli araç", "SORUNUZ"),
    ("860 araç lazım", "SORUNUZ"),
    ("Tel: 05372821128", "SORUNUZ"),
    ("Beni 0537 282 11 28 den arayın", "SORUNUZ"),
    ("Fiyat için 0534 253 01 65", "SORUNUZ")
]

for inp, exp in tests:
    res = _extract_price_regex(inp)
    print(f"Input: {inp:20} | Result: {res:10} | Expected: {exp:10} | {'OK' if res==exp else 'FAIL'}")
