# -*- coding: utf-8 -*-
"""
Tip dönüştürme ve metin işleme yardımcı fonksiyonları
"""
import re
from typing import List, Optional, Any
import unicodedata


def normalize_text(text: str) -> str:
    """
    Metni normalize eder (Türkçe karakterler korunur, büyük harf yapılır).
    
    Args:
        text: Normalize edilecek metin
        
    Returns:
        str: Normalize edilmiş metin
    """
    if not text:
        return ""
    
    # Türkçe karakterleri koruyarak büyük harfe çevir
    turkish_upper = {
        'ı': 'I', 'i': 'İ', 'ğ': 'Ğ', 'ü': 'Ü',
        'ş': 'Ş', 'ö': 'Ö', 'ç': 'Ç'
    }
    
    result = text
    for lower, upper in turkish_upper.items():
        result = result.replace(lower, upper)
    
    return result.upper().strip()


def parse_type_string(value: Any) -> List[str]:
    """
    Tip stringini listeye dönüştürür.
    
    Args:
        value: String, liste veya None olabilir
        
    Returns:
        List[str]: Tip listesi
    """
    if value is None:
        return []
    
    if isinstance(value, list):
        return [str(v).strip() for v in value if v]
    
    if isinstance(value, str):
        # Virgül, tire veya boşlukla ayrılmış olabilir
        separators = [',', '/', '-', ';']
        result = [value]
        
        for sep in separators:
            new_result = []
            for item in result:
                new_result.extend(item.split(sep))
            result = new_result
        
        return [item.strip() for item in result if item.strip()]
    
    return [str(value)]


def ensure_type_list(value: Any, normalize: bool = True) -> List[str]:
    """
    Değerin liste formatında olduğundan emin olur.
    
    Args:
        value: Dönüştürülecek değer
        normalize: True ise metinleri normalize et
        
    Returns:
        List[str]: Liste formatında değer
    """
    result = parse_type_string(value)
    
    if normalize:
        result = [normalize_text(item) for item in result]
    
    return result


def deduplicate_list(items: List[str], case_insensitive: bool = True) -> List[str]:
    """
    Listeden tekrar eden elemanları kaldırır.
    
    Args:
        items: Temizlenecek liste
        case_insensitive: True ise büyük/küçük harf duyarsız karşılaştırma
        
    Returns:
        List[str]: Tekrarsız liste
    """
    if not items:
        return []
    
    seen = set()
    result = []
    
    for item in items:
        key = item.upper() if case_insensitive else item
        if key not in seen:
            seen.add(key)
            result.append(item)
    
    return result


def clean_phone_number(phone: str) -> str:
    """
    Telefon numarasını temizler.
    
    Args:
        phone: Ham telefon numarası
        
    Returns:
        str: Temizlenmiş telefon numarası
    """
    if not phone:
        return ""
    
    # Sadece rakamları al
    digits = re.sub(r'\D', '', str(phone))
    
    # Türkiye formatına çevir
    if digits.startswith('90') and len(digits) == 12:
        return digits
    elif digits.startswith('0') and len(digits) == 11:
        return '90' + digits[1:]
    elif len(digits) == 10:
        return '90' + digits
    
    return digits


def remove_emojis(text: str) -> str:
    """
    Metinden emojileri kaldırır.
    
    Args:
        text: Emoji içerebilecek metin
        
    Returns:
        str: Emojisiz metin
    """
    if not text:
        return ""
    
    # Unicode emoji kategorilerini kaldır
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    
    return emoji_pattern.sub('', text)
