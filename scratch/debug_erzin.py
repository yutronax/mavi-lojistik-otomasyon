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
        
        # New logic: Exclude sensitive numbers only if no keyword nearby
        if val_norm in ['13.60', '1360', '860']:
            surrounding_small = clean_text[max(0, m.start()-10):min(len(clean_text), m.end()+10)]
            has_price_kw = any(kw in surrounding_small for kw in ['TL', 'KDV', 'FIYAT', 'HESAP'])
            if not has_price_kw:
                continue
                
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

msg = """📍Erzin ➝ Çumra 860+Kdv
📍Erzin ➝ Cihanbeyli 900+kdv"""

lines = msg.split('\n')
print(f"Line 1: {lines[0]} -> Price: {_extract_price_regex(lines[0])}")
print(f"Line 2: {lines[1]} -> Price: {_extract_price_regex(lines[1])}")
