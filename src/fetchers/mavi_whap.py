# -*- coding: utf-8 -*-
# openai_final_batch.py
"""
OpenAI Parser - Tam Entegre Versiyon

Ã–zellikler:
1. VehicleTypeMatcher: AraÃƒÂ§/kasa/yÃƒÂ¼k tipi eÃ…Å¸leÃ…Å¸tirme (gemini_final_batch'dan import)
2. LocationMatcher: Ã„Â°l/ilÃƒÂ§e eÃ…Å¸leÃ…Å¸tirme ve validasyon (gemini_final_batch'dan import)
3. OpenAI API entegrasyonu
4. Mesaj parÃƒÂ§alama ve liste formatÃ„Â± desteÃ„Å¸i
"""

import os
import json
import re
from typing import List, Dict, Optional, Tuple
from pydantic import BaseModel, Field

# Gemini client (Gemini-only)
try:
    from src.utils.gemini_adapter import GeminiClient
    GEMINI_AVAILABLE = True
    OPENAI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    OPENAI_AVAILABLE = False
    logger.debug("Gemini client not available")

# Matcher and helper imports (moved out of gemini_final_batch)
try:
    from src.utils.enhanced_vehicle_matcher import VehicleTypeMatcher
except Exception:
    VehicleTypeMatcher = None

try:
    from src.utils.advanced_location_matcher import LocationMatcher
except Exception:
    LocationMatcher = None

try:
    from src.parsers.shipment_models import Shipment, ShipmentList, validate_type_values, load_json_file
except Exception:
    Shipment = None
    ShipmentList = None
    validate_type_values = None
    load_json_file = None

from src.utils.common import get_root_path
import logging
logger = logging.getLogger(__name__)

# ============================================================================
# OPENAI API ENTEGRASYONU
# ============================================================================

def _split_message_into_chunks(message_body: str, max_chunk_length: int = 1500) -> List[str]:
    """
    MesajÃ„Â± daha kÃƒÂ¼ÃƒÂ§ÃƒÂ¼k parÃƒÂ§alara bÃƒÂ¶ler.
    SatÃ„Â±r sonlarÃ„Â±na gÃƒÂ¶re bÃƒÂ¶ler, bÃƒÂ¶ylece sevkiyat bilgileri bÃƒÂ¶lÃƒÂ¼nmez.
    
    Args:
        message_body: BÃƒÂ¶lÃƒÂ¼necek mesaj
        max_chunk_length: Her parÃƒÂ§anÃ„Â±n maksimum uzunluÃ„Å¸u (karakter)
    
    Returns:
        List[str]: Mesaj parÃƒÂ§alarÃ„Â±
    """
    if len(message_body) <= max_chunk_length:
        return [message_body]
    
    lines = message_body.split('\n')
    
    # Liste formatÃ„Â± kontrolÃƒÂ¼: EÃ„Å¸er ÃƒÂ§oÃ„Å¸u satÃ„Â±r sevkiyat formatÃ„Â±nda gÃƒÂ¶rÃƒÂ¼nÃƒÂ¼yorsa (ÃƒÂ¶rn: "Ã„Â°L - Ã„Â°L" veya "Ã„Â°L Ã¢â€ â€™ Ã„Â°L")
    # Her satÃ„Â±rÃ„Â± ayrÃ„Â± bir chunk olarak iÃ…Å¸le (daha iyi parÃƒÂ§alama iÃƒÂ§in)
    shipment_pattern = re.compile(r'^[A-ZÃƒâ€¡Ã„Å¾Ã„Â°Ãƒâ€“Ã…Å¾ÃƒÅ“\s]+[-Ã¢â€ â€™Ã¢Å¾Â¡]\s*[A-ZÃƒâ€¡Ã„Å¾Ã„Â°Ãƒâ€“Ã…Å¾ÃƒÅ“\s]+', re.IGNORECASE)
    shipment_lines = sum(1 for line in lines if line.strip() and shipment_pattern.search(line.strip()))
    
    # EÃ„Å¸er satÃ„Â±rlarÃ„Â±n %60'Ã„Â±ndan fazlasÃ„Â± sevkiyat formatÃ„Â±ndaysa, liste formatÃ„Â± olarak kabul et
    if len(lines) > 2 and shipment_lines / len([l for l in lines if l.strip()]) > 0.6:
        # Liste formatÃ„Â±: Her satÃ„Â±rÃ„Â± ayrÃ„Â± chunk yap (ama ÃƒÂ§ok kÃƒÂ¼ÃƒÂ§ÃƒÂ¼k chunk'larÃ„Â± birleÃ…Å¸tir)
        chunks = []
        current_chunk = []
        current_length = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            line_length = len(line) + 1  # +1 for newline
            
            # EÃ„Å¸er satÃ„Â±r ÃƒÂ§ok uzunsa, yine de bÃƒÂ¶l
            if line_length > max_chunk_length:
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                # Uzun satÃ„Â±rÃ„Â± kelimelere bÃƒÂ¶l
                words = line.split()
                current_line = []
                for word in words:
                    word_length = len(word) + 1
                    if current_length + word_length > max_chunk_length and current_line:
                        chunks.append('\n'.join(current_chunk) + '\n' + ' '.join(current_line))
                        current_chunk = []
                        current_line = [word]
                        current_length = word_length
                    else:
                        current_line.append(word)
                        current_length += word_length
                if current_line:
                    current_chunk.append(' '.join(current_line))
            else:
                # Normal satÃ„Â±r: EÃ„Å¸er eklenirse max_chunk_length'i aÃ…Å¸acaksa, mevcut chunk'Ã„Â± kaydet
                if current_length + line_length > max_chunk_length and current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = [line]
                    current_length = line_length
                else:
                    current_chunk.append(line)
                    current_length += line_length
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks if chunks else [message_body]
    
    # Normal bÃƒÂ¶lme mantÃ„Â±Ã„Å¸Ã„Â±
    chunks = []
    current_chunk = []
    current_length = 0
    
    for line in lines:
        line_length = len(line) + 1  # +1 for newline
        
        # EÃ„Å¸er tek bir satÃ„Â±r bile max_chunk_length'den uzunsa, zorla bÃƒÂ¶l
        if line_length > max_chunk_length:
            # Mevcut chunk'Ã„Â± kaydet
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
            
            # Uzun satÃ„Â±rÃ„Â± kelimelere bÃƒÂ¶l
            words = line.split()
            current_line = []
            for word in words:
                word_length = len(word) + 1
                if current_length + word_length > max_chunk_length and current_line:
                    chunks.append('\n'.join(current_chunk) + '\n' + ' '.join(current_line))
                    current_chunk = []
                    current_line = [word]
                    current_length = word_length
                else:
                    current_line.append(word)
                    current_length += word_length
            
            if current_line:
                current_chunk.append(' '.join(current_line))
        else:
            # Normal satÃ„Â±r ekleme
            if current_length + line_length > max_chunk_length and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length
    
    # Son chunk'Ã„Â± ekle
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks if chunks else [message_body]


_ROUTE_ARROWS = [
    'Ã¢Å¾Â¡', 'Ã¢Å¾Å“', 'Ã¢Å¾Â', 'Ã¢Å¾Å¾', 'Ã¢Å¾Å¸', 'Ã¢Å¾ ', 'Ã¢Å¾Â¢', 'Ã¢Å¾Â£', 'Ã¢Å¾Â¤', 'Ã¢Å¾Â¥', 'Ã¢Å¾Â§', 'Ã¢Å¾Â¨', 'Ã¢Å¾Â©',
    'Ã¢Å¾Âª', 'Ã¢Å¾Â®', 'Ã¢Å¾Â¯', 'Ã¢Å¾Â±', 'Ã¢Å¾Â²', 'Ã¢Å¾Â³', 'Ã¢Å¾Âµ', 'Ã¢Å¾Â¸', 'Ã¢Å¾Â»', 'Ã¢Å¾Â¼', 'Ã¢Å¾Â½', 'Ã¢Å¾Â¾',
    'Ã¢â€ â€™', 'Ã¢â€¡â€™', 'Ã¢Å¸Â¶', 'Ã¢Å¸Â¹', 'Ã¢Å¸Âº', 'Ã¢Å¸Â¾', 'Ã¢Å¸Â¿', 'Ã¢â€ Â¦', 'Ã¢â€  ', 'Ã¢â€ Â£', 'Ã¢â€ Âª', 'Ã¢â€ Â¬', 'Ã¢â€ Â',
    '=>', '->', '=>>', '-->'
]

_DETAIL_KEYWORDS = {
    'FRIGO', 'FRÃ„Â°GO', 'TERMOKIN', 'TERMOKÃ„Â°N', 'SOGUK', 'SOÃ„Å¾UK',
    'AÃƒâ€¡IK', 'ACIK', 'KAPALI', 'TENTELI', 'TENTELÃ„Â°', 'TIR', 'TI',
    'KAMYON', 'KAMYONET', 'TANKER', 'LOWBET', 'LOW-BED', 'LOWBED',
    'SAL', 'DORSE', 'DORSELÃ„Â°', 'DAMPER', 'DAMPERLI', 'DAMPERLÃ„Â°',
    'PLATFORM', 'KONTEYNER', 'PARSÃ„Â°YEL', 'PARÃƒâ€¡ALÃ„Â°', 'PARÃƒâ€¡A', 'KOMPLE'
}


def _normalize_route_separators(line: str) -> str:
    normalized = line
    for arrow in _ROUTE_ARROWS:
        if arrow in normalized:
            normalized = normalized.replace(arrow, ' -> ')
    # Tire ( - ) veya uzun tire (Ã¢â‚¬â€œ Ã¢â‚¬â€) ile ayrÃ„Â±lanlarÃ„Â± normalize et
    normalized = re.sub(r'\s+[Ã¢â‚¬ÂÃ¢â‚¬â€˜Ã¢â‚¬â€™Ã¢â‚¬â€œÃ¢â‚¬â€]+\s+', ' -> ', normalized)
    return normalized


def _clean_location_fragment(fragment: str) -> str:
    if not fragment:
        return ''
    cleaned = fragment.strip()
    cleaned = re.sub(r'^[\*\Ã¢â‚¬Â¢\Ã‚Â·\-\d\)\(]+\s*', '', cleaned)
    cleaned = cleaned.strip(" .,:;|/\\")
    return cleaned


def _split_destination_and_details(text: str) -> Tuple[str, str]:
    if not text:
        return '', ''
    tokens = text.split()
    destination_tokens = []
    detail_tokens = []
    detail_started = False
    for token in tokens:
        token_clean = re.sub(r'[^A-ZÃƒâ€¡Ã„Å¾Ã„Â°Ãƒâ€“Ã…Å¾ÃƒÅ“0-9]', '', token.upper())
        if not detail_started:
            is_detail_token = (
                token_clean in _DETAIL_KEYWORDS or
                any(token_clean.startswith(keyword) for keyword in _DETAIL_KEYWORDS)
            )
            if is_detail_token:
                detail_started = True
        if detail_started:
            detail_tokens.append(token)
        else:
            destination_tokens.append(token)
    destination = ' '.join(destination_tokens).strip(" ,.;")
    details = ' '.join(detail_tokens).strip(" ,.;")
    return destination, details


def _infer_kasa_types(detail_text: str) -> List[str]:
    if not detail_text:
        return []
    text_upper = detail_text.upper()
    if any(keyword in text_upper for keyword in ['FRIGO', 'FRÃ„Â°GO', 'TERMOK', 'SOÃ„Å¾UK', 'SOGUK']):
        return ['FRÃ„Â°GO']
    if 'TENTEL' in text_upper or 'KAPALI' in text_upper:
        return ['KAPALI']
    if 'AÃƒâ€¡IK' in text_upper or 'ACIK' in text_upper or 'DAMPER' in text_upper or 'SAL' in text_upper:
        return ['AÃƒâ€¡IK']
    return []


def _infer_yuk_types(detail_text: str) -> List[str]:
    if not detail_text:
        return []
    text_upper = detail_text.upper()
    if 'PARÃƒâ€¡A' in text_upper or 'PARCA' in text_upper or 'PARSÃ„Â°YEL' in text_upper or 'PARSÃ„Â°YAL' in text_upper:
        return ['PARÃƒâ€¡A']
    if 'KOMPLE' in text_upper:
        return ['KOMPLE']
    return []


def _resolve_location(location_matcher, fragment: str) -> Optional[Dict[str, str]]:
    if not location_matcher or not fragment or not fragment.strip():
        return None
    parsed = location_matcher.parse_location(fragment)
    if not parsed or not parsed.get('il'):
        return None
    validated = location_matcher.validate_and_fix(parsed.get('il', ''), parsed.get('ilce', ''), fragment)
    if not validated.get('il'):
        return None
    return validated


def _fallback_parse_simple_routes(message_body: str, message_id: str, location_matcher) -> List[Dict]:
    if not location_matcher:
        return []
    shipments = []
    seen_routes = set()
    lines = message_body.splitlines()
    candidate_lines = []
    for raw_line in lines:
        if not raw_line or not raw_line.strip():
            continue
        normalized_line = _normalize_route_separators(raw_line)
        if '->' not in normalized_line:
            continue
        left, right = normalized_line.split('->', 1)
        left_clean = _clean_location_fragment(left)
        right_clean = right.strip()
        if len(left_clean) < 2 or len(right_clean) < 2:
            continue
        dest_text, detail_text = _split_destination_and_details(right_clean)
        dest_clean = _clean_location_fragment(dest_text)
        if len(dest_clean) < 2:
            continue
        candidate_lines.append((raw_line, left_clean, dest_clean, detail_text))
    if not candidate_lines:
        return []
    for raw_line, from_fragment, to_fragment, detail in candidate_lines:
        start_location = _resolve_location(location_matcher, from_fragment)
        end_location = _resolve_location(location_matcher, to_fragment)
        if not start_location or not end_location:
            continue
        route_key = (
            start_location.get('il', ''), start_location.get('ilce', ''),
            end_location.get('il', ''), end_location.get('ilce', ''),
            detail.upper()
        )
        if route_key in seen_routes:
            continue
        seen_routes.add(route_key)
        kasa_tipi = _infer_kasa_types(detail)
        yuk_tipi = _infer_yuk_types(detail)
        shipment_data = {
            'isim': '',
            'nereden_il': start_location.get('il', ''),
            'nereden_ilce': start_location.get('ilce', ''),
            'nereye_il': end_location.get('il', ''),
            'nereye_ilce': end_location.get('ilce', ''),
            'arac_tipi': ['1360'],
            'kasa_tipi': kasa_tipi or ['AÃƒâ€¡IK', 'KAPALI'],
            'yuk_tipi': yuk_tipi or ['KOMPLE'],
            'fiyat': 'SORUNUZ',
            'telefon': '',
            'aciklama': detail.strip(),
            'message_id': message_id
        }
        try:
            shipment = Shipment(**shipment_data)
            shipments.append(shipment.model_dump())
        except Exception as e:
            logger.debug(f"  Ã¢â€â€Ã¢â€â‚¬ [Ã¢Å¡ Ã¯Â¸Â] Basit liste fallback'inde satÃ„Â±r atlandÃ„Â±: {e} | SatÃ„Â±r: {raw_line.strip()}")
    if shipments:
        logger.debug(f"[Ã°Å¸â€º Ã¯Â¸Â] LLM sevkiyat dÃƒÂ¶ndÃƒÂ¼rmedi, liste fallback'i ile {len(shipments)} sevkiyat oluÃ…Å¸turuldu")
    return shipments


def _extract_global_type_section(text: str, max_lines: int = 5) -> str:
    """MesajÃ„Â±n baÃ…Å¸Ã„Â±ndaki global tip ipuÃƒÂ§larÃ„Â±nÃ„Â± dÃƒÂ¶ndÃƒÂ¼r."""
    if not text:
        return ""
    lines: List[str] = []
    for raw in text.splitlines():
        clean = raw.strip()
        if clean:
            lines.append(clean)
        if len(lines) >= max_lines:
            break
    return '\n'.join(lines)


def _process_single_chunk(chunk: str, message_id: str, client, location_matcher, 
                         valid_iller: List[str], iller_listesi: str, model_name: str = "gpt-4o-mini") -> List[Dict]:
    """
    Tek bir mesaj parÃƒÂ§asÃ„Â±nÃ„Â± OpenAI ile iÃ…Å¸ler.
    
    Args:
        chunk: Ã„Â°Ã…Å¸lenecek mesaj parÃƒÂ§asÃ„Â±
        message_id: Mesaj ID
        client: OpenAI client instance
        location_matcher: LocationMatcher instance
        valid_iller: GeÃƒÂ§erli il listesi
        iller_listesi: Ã„Â°ller listesi string'i
        model_name: OpenAI model adÃ„Â± (varsayÃ„Â±lan: gpt-4o-mini)
    
    Returns:
        List[Dict]: AyrÃ„Â±Ã…Å¸tÃ„Â±rÃ„Â±lmÃ„Â±Ã…Å¸ sevkiyat listesi
    """
    global_types_section = _extract_global_type_section(chunk)
    
    prompt = f"""AÃ…Å¸aÃ„Å¸Ã„Â±daki WhatsApp mesajÃ„Â±ndan lojistik sevkiyat bilgilerini ÃƒÂ§Ã„Â±kar.

MESAJ:
{chunk}

GLOBAL TÃ„Â°P Ã„Â°PUÃƒâ€¡LARI (mesajÃ„Â±n baÃ…Å¸Ã„Â±):
{global_types_section}

KRÃ„Â°TÃ„Â°K KURALLAR:
1. EMOJÃ„Â° VE Ãƒâ€“ZEL KARAKTERLER: Mesajda Ã¢Ââ€, Ã¢Å¾Â¡, *, vb. gibi emoji ve ÃƒÂ¶zel karakterler olabilir. 
   BUNLARI TAMAMEN GÃƒâ€“RMEZDEN GEL! Sadece lojistik bilgileri ÃƒÂ§Ã„Â±kar.
   Ãƒâ€“rnek: "Ã¢Ââ€Ã¢Ââ€*FRÃ„Â°GO | +4 DERECE*Ã¢Ââ€Ã¢Ââ€" Ã¢â€ â€™ sadece "FRÃ„Â°GO" bilgisini al, emojileri yok say.

2. GÃƒÅ“ZERGAH TESPÃ„Â°TÃ„Â°: "Ã¢Å¾Â¡", "Ã¢â€ â€™", "-", "Ã¢â‚¬â€œ" gibi iÃ…Å¸aretler gÃƒÂ¼zergah belirtir.
   Ãƒâ€“rnek: "LÃƒÂ¼leburgaz Ã¢Å¾Â¡ Silivri" Ã¢â€ â€™ nereden_il: LÃƒÅ“LEBURGAZ, nereye_il: SÃ„Â°LÃ„Â°VRÃ„Â°

3. TELEFON NUMARALARI: TÃƒÂ¼m telefon numaralarÃ„Â±nÃ„Â± topla ve telefon alanÃ„Â±na ekle.
   Ãƒâ€“rnek: "*0 506 156 32 10*" ve "*0 555 028 32 06*" Ã¢â€ â€™ telefon: "0 506 156 32 10, 0 555 028 32 06"

4. FÃ„Â°RMA/KÃ„Â°Ã…Å¾Ã„Â° ADI: MesajÃ„Â±n sonunda veya baÃ…Å¸Ã„Â±nda firma/kiÃ…Å¸i adÃ„Â± olabilir.
   Ãƒâ€“rnek: "*FASTLOG LOJÃ„Â°STÃ„Â°K*" Ã¢â€ â€™ isim: "FASTLOG LOJÃ„Â°STÃ„Â°K"

5. ARAÃƒâ€¡/KASA TÃ„Â°PÃ„Â°: "Frigo TÃ„Â±r", "Tenteli", "AÃƒÂ§Ã„Â±k", "KapalÃ„Â±" gibi ifadeleri algÃ„Â±la.
   Ãƒâ€“rnek: "Frigo TÃ„Â±r" Ã¢â€ â€™ kasa_tipi: ["FRÃ„Â°GO"], arac_tipi: ["1360"]

Ãƒâ€¡Ã„Â±karÃ„Â±lmasÃ„Â± gereken bilgiler:
- isim: KiÃ…Å¸i veya firma adÃ„Â± (varsa, EMOJÃ„Â° VE Ãƒâ€“ZEL KARAKTERLERÃ„Â° Ãƒâ€¡IKAR)
- nereden_il: KalkÃ„Â±Ã…Å¸ ili (BÃƒÅ“YÃƒÅ“K HARF, ZORUNLU - AÃ…Å¾AÃ„Å¾IDAKÃ„Â° Ã„Â°LLERDEN BÃ„Â°RÃ„Â° OLMALI)
- nereden_ilce: KalkÃ„Â±Ã…Å¸ ilÃƒÂ§esi (ZORUNLU - Ã„Â°lin ilÃƒÂ§elerinden biri olmalÃ„Â±, eÃ„Å¸er mesajda yoksa varsayÃ„Â±lan ilÃƒÂ§eyi kullan)
- nereye_il: VarÃ„Â±Ã…Å¸ ili (BÃƒÅ“YÃƒÅ“K HARF, ZORUNLU - AÃ…Å¾AÃ„Å¾IDAKÃ„Â° Ã„Â°LLERDEN BÃ„Â°RÃ„Â° OLMALI)
- nereye_ilce: VarÃ„Â±Ã…Å¸ ilÃƒÂ§esi (ZORUNLU - Ã„Â°lin ilÃƒÂ§elerinden biri olmalÃ„Â±, eÃ„Å¸er mesajda yoksa varsayÃ„Â±lan ilÃƒÂ§eyi kullan)
- arac_tipi: AraÃƒÂ§ tipi (liste olarak, ÃƒÂ¶rn: ["1360"] - varsayÃ„Â±lan: ["1360"])
- kasa_tipi: Kasa tipi (liste olarak, ÃƒÂ¶rn: ["FRÃ„Â°GO"], ["AÃƒâ€¡IK"], ["KAPALI"] - varsayÃ„Â±lan: ["AÃƒâ€¡IK", "KAPALI"])
- yuk_tipi: YÃƒÂ¼k tipi (liste olarak, ÃƒÂ¶rn: ["KOMPLE"] - varsayÃ„Â±lan: ["KOMPLE"])
- fiyat: Fiyat bilgisi (varsayÃ„Â±lan: "SORUNUZ")
- telefon: Telefon numarasÃ„Â±(larÃ„Â±) - TÃƒÅ“M NUMARALARI TOPLA, virgÃƒÂ¼lle ayÃ„Â±r (varsa)
- aciklama: Ek aÃƒÂ§Ã„Â±klama (varsa, EMOJÃ„Â°LERÃ„Â° Ãƒâ€¡IKAR)

Ãƒâ€“NEMLÃ„Â° KURALLAR:
1. nereden_il ve nereye_il KESÃ„Â°NLÃ„Â°KLE aÃ…Å¸aÃ„Å¸Ã„Â±daki geÃƒÂ§erli illerden biri olmalÃ„Â±
2. nereden_ilce ve nereye_ilce KESÃ„Â°NLÃ„Â°KLE ilin ilÃƒÂ§elerinden biri olmalÃ„Â±
3. EÃ„Å¸er mesajda sadece ilÃƒÂ§e yazÃ„Â±yorsa (ÃƒÂ¶rn: "Gebze", "Biga"), o ilÃƒÂ§enin baÃ„Å¸lÃ„Â± olduÃ„Å¸u ili de bul ve yaz
4. Ã„Â°l ve ilÃƒÂ§e alanlarÃ„Â± ASLA null veya boÃ…Å¸ kalmamalÃ„Â±
5. EÃ„Å¸er mesajda birden fazla gÃƒÂ¼zergah varsa (her satÃ„Â±r veya "Ã¢â€ â€™", "-", "Ã¢Å¾Â¡" ile ayrÃ„Â±lmÃ„Â±Ã…Å¸), HER BÃ„Â°RÃ„Â° Ã„Â°Ãƒâ€¡Ã„Â°N AYRI SEVKIYAT OLUÃ…Å¾TUR
6. SATIR GEÃ„â€¡Ã„Â°Ã…Å¾LERÃ„Â°: BazÃ„Â± sevkiyatlarda bilgiler (ÃƒÂ¶rn: araÃƒÂ§ tipi, fiyat) bir alt satÃ„Â±ra kaymÃ„Â±Ã…Å¾ olabilir. Alt satÃ„Â±rdaki bilgi bir ÃƒÂ¶nceki gÃƒÂ¼zergahla iliÃ…Å¸kiliyse onu aynÃ„Â± sevkiyata dahil et.
7. AYIRAÃƒâ€¡LAR: "Damperli/TÃ„Â±r", "TÃ„Â±r-Kamyon" gibi "/" veya "-" ile ayrÃ„Â±lmÃ„Â±Ã…Å¾ tÃƒÂ¼m tipleri algÃ„Â±la ve listeye ekle.
8. Aciklama ve isim alanlarÃ„Â±na emoji KOYMA, sadece metin yaz
9. Telefon numaralarÃ„Â±nÃ„Â± topla: TÃƒÂ¼m numaralarÃ„Â± bul ve virgÃƒÂ¼lle ayÃ„Â±rarak telefon alanÃ„Â±na ekle

KRÃ„Â°TÃ„Â°K - SATIR BAZLI TÃ„Â°P TESPÃ„Â°TÃ„Â°:
1. MESAJIN HER SATIRINI AYRI ANALÃ„Â°Z ET.
2. SatÃ„Â±rda kasa/araÃƒÂ§/yÃƒÂ¼k tipini belirten kelimeler (AÃƒâ€¡IK, KAPALI, TENTELÃ„Â°, FRÃ„Â°GO, TERMOKÃ„Â°N, SOÃ„Å¾UK, 1360, 860, 40 AYAK, 10 TEKER, vb.) varsa:
   - O satÃ„Â±r iÃƒÂ§in SADECE bu kelimelerin tanÃ„Â±mladÃ„Â±Ã„Å¸Ã„Â± tipleri kullan.
   - Global tip ipuÃƒÂ§larÃ„Â±nÃ„Â± bu satÃ„Â±r iÃƒÂ§in kullanma.
3. SatÃ„Â±rda tip kelimesi YOKSA:
   - Global tip ipuÃƒÂ§larÃ„Â±nda belirtilen kasa/araÃƒÂ§/yÃƒÂ¼k tiplerini kullan (ÃƒÂ¶rn: "AraÃƒÂ§lar aÃƒÂ§Ã„Â±k veya kapalÃ„Â± 13.60").
4. SatÃ„Â±rda sadece kasa tipi belirtilmiÃ…Å¸se kasa satÃ„Â±rdan, araÃƒÂ§/yÃƒÂ¼k globalden alÃ„Â±nabilir.
5. SatÃ„Â±rda sadece araÃƒÂ§ tipi belirtilmiÃ…Å¸se araÃƒÂ§ satÃ„Â±rdan, kasa/yÃƒÂ¼k globalden alÃ„Â±nabilir.

TÃ„Â°P ALGILAMA:
- KASA: AÃƒâ€¡IK, ACIK, KAPALI, TENTELÃ„Â°, TENTELI, FRÃ„Â°GO, FRIGO, TERMOKÃ„Â°N, TERMOKIN, SOÃ„Å¾UK, SOGUK
- ARAÃƒâ€¡: 1360, 13.60, 13,60, TIR, TIR, 860, 8.60, 8,60, 40 AYAK, 40AYAK, 10 TEKER, 10TEKER
- YÃƒÅ“K: KOMPLE, PARÃƒâ€¡A, PARCA, PALETLÃ„Â°, PALETLÃ„Â°

Ãƒâ€“RNEKLER:
- SatÃ„Â±r: "ElazÃ„Â±Ã„Å¸ dan Mardin Nusaybin KAPALI 13.60" Ã¢â€ â€™ kasa_tipi ["KAPALI"], arac_tipi ["1360"]
- SatÃ„Â±r: "ElazÃ„Â±Ã„Å¸ dan Ã„Â°zmir Bergama \n DAMPERLÃ„Â° TIR" Ã¢â€ â€™ kasa_tipi ["AÃƒâ€¡IK"], arac_tipi ["1360"] (Damperli TÃ„Â±r alt satÃ„Â±rda olsa bile yakala)
- SatÃ„Â±r: "Ankara -> Bolu DAMPERLÃ„Â°/TIR" Ã¢â€ â€™ kasa_tipi ["AÃƒâ€¡IK"], arac_tipi ["1360"]

Ãƒâ€“RNEK MESAJ:
Ã¢Ââ€Ã¢Ââ€*FRÃ„Â°GO | +4 DERECE*Ã¢Ââ€Ã¢Ââ€
LÃƒÂ¼leburgaz Ã¢Å¾Â¡ Silivri Frigo TÃ„Â±r
*0 506 156 32 10*
*0 555 028 32 06*
*FASTLOG LOJÃ„Â°STÃ„Â°K*

Ãƒâ€¡IKTI:
{{
  "shipments": [
    {{
      "isim": "FASTLOG LOJÃ„Â°STÃ„Â°K",
      "nereden_il": "KIRKLARELÃ„Â°",
      "nereden_ilce": "LÃƒÂ¼leburgaz",
      "nereye_il": "Ã„Â°STANBUL",
      "nereye_ilce": "Silivri",
      "arac_tipi": ["1360"],
      "kasa_tipi": ["FRÃ„Â°GO"],
      "yuk_tipi": ["KOMPLE"],
      "fiyat": "SORUNUZ",
      "telefon": "0 506 156 32 10, 0 555 028 32 06",
      "aciklama": "",
      "message_id": "{message_id}"
    }}
  ]
}}

GEÃƒâ€¡ERLÃ„Â° Ã„Â°LLER (SADECE BUNLARI KULLAN):
{iller_listesi}

Ãƒâ€¡Ã„Â±ktÃ„Â±yÃ„Â± JSON formatÃ„Â±nda dÃƒÂ¶ndÃƒÂ¼r. EÃ„Å¸er birden fazla sevkiyat varsa, hepsini listele.
Her sevkiyat iÃƒÂ§in message_id alanÃ„Â±nÃ„Â± "{message_id}" olarak ayarla.

SADECE GEÃƒâ€¡ERLÃ„Â° JSON DÃƒâ€“NDÃƒÅ“R, BAÃ…Å¾KA BÃ„Â°R Ã…Å¾EY YAZMA!
Format: {{"shipments": [{{...}}, {{...}}]}}
"""
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "Sen bir lojistik sevkiyat bilgisi ÃƒÂ§Ã„Â±karma uzmanÃ„Â±sÃ„Â±n. Mesajlardan sevkiyat bilgilerini JSON formatÃ„Â±nda ÃƒÂ§Ã„Â±karÃ„Â±rsÃ„Â±n."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=2048,
            response_format={"type": "json_object"} if model_name.startswith("gpt-4") else None
        )
        
        response_text = ""
        if response.choices and len(response.choices) > 0:
            response_text = response.choices[0].message.content.strip()
        
        if not response_text:
            return []
        
        # Markdown code block temizle
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        # JSON parse
        try:
            result = json.loads(response_text)
            shipments_data = result.get("shipments", [])
            if not isinstance(shipments_data, list):
                shipments_data = [shipments_data] if shipments_data else []
            return shipments_data
        except json.JSONDecodeError:
            # JSON parse hatasÃ„Â± - basit dÃƒÂ¼zeltme denemeleri
            try:
                json_start = response_text.find('{')
                if json_start != -1:
                    json_end = response_text.rfind('}')
                    if json_end > json_start:
                        json_str = response_text[json_start:json_end+1]
                        result = json.loads(json_str)
                        shipments_data = result.get("shipments", [])
                        if not isinstance(shipments_data, list):
                            shipments_data = [shipments_data] if shipments_data else []
                        return shipments_data
            except:
                pass
            return []
    
    except Exception as e:
        error_str = str(e)
        # Quota/Rate limit hatasÃ„Â± kontrolÃƒÂ¼
        if '429' in error_str or 'rate_limit' in error_str.lower() or 'quota' in error_str.lower():
            logger.debug(f"[Ã¢Å¡ Ã¯Â¸Â] Chunk iÃ…Å¸lenirken rate limit hatasÃ„Â±: {error_str}")
            # API key rotasyonu iÃƒÂ§in exception'Ã„Â± yukarÃ„Â± fÃ„Â±rlat
            raise Exception(f"RATE_LIMIT_ERROR: {error_str}")
        logger.error(f"[Ã¢Å¡ Ã¯Â¸Â] Chunk iÃ…Å¸lenirken hata: {e}")
        return []


def extract_shipments_with_openai(message_dict: Dict, model_name: str = "gpt-4o-mini") -> List[Dict]:
    """
    OpenAI API kullanarak mesajdan sevkiyatlarÃ„Â± ÃƒÂ§Ã„Â±kar
    
    Args:
        message_dict: WhatsApp mesajÃ„Â± dictionary'si
        model_name: OpenAI model adÃ„Â± (varsayÃ„Â±lan: gpt-4o-mini, alternatif: gpt-4o, gpt-3.5-turbo)
    
    Returns:
        List[Dict]: AyrÃ„Â±Ã…Å¸tÃ„Â±rÃ„Â±lmÃ„Â±Ã…Å¸ sevkiyat listesi
    """
    if not OPENAI_AVAILABLE:
        logger.debug("[Ã¢ÂÅ’] OpenAI API kullanÃ„Â±lamÃ„Â±yor. openai paketi yÃƒÂ¼klÃƒÂ¼ deÃ„Å¸il.")
        return []
    
    if not LocationMatcher or not Shipment:
        logger.debug("[Ã¢ÂÅ’] Gerekli modÃƒÂ¼ller yÃƒÂ¼klenemedi (LocationMatcher, Shipment)")
        return []
    
    try:
        root_dir = get_root_path()
        yuk_tipi_file = os.path.join(root_dir, 'yuk_tipi.json')
        il_ilce_file = os.path.join(root_dir, 'il_ilÃƒÂ§eler.json')
        
        yuk_tipi_table = load_json_file(yuk_tipi_file)
        il_ilce_data = load_json_file(il_ilce_file)
        
        message_body = message_dict.get("body", "")
        message_id = message_dict.get("id", "")
        
        if not message_body or not message_body.strip():
            logger.debug(f"[Ã¢Å¡ Ã¯Â¸Â] Mesaj body boÃ…Å¸: {message_id}")
            return []
        
        # MesajÃ„Â± temizle: BaÃ…Å¸ta ve sonda boÃ…Å¸ satÃ„Â±rlarÃ„Â± kaldÃ„Â±r, ama iÃƒÂ§eriÃ„Å¸i koru
        message_body = message_body.strip()
        
        # API key'i environment variable'dan al (Gemini-only)
        api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        
        if not api_key:
            logger.debug("[] GEMINI_API_KEY veya GOOGLE_API_KEY bulunamadı. Lütfen GEMINI_API_KEY ayarlayın.")
            return []
        
        client = OpenAI(api_key=api_key)
        
        location_matcher = LocationMatcher(il_ilce_data)
        
        valid_iller = [entry['il'] for entry in il_ilce_data]
        iller_listesi = ', '.join(sorted(valid_iller))
        
        # MesajÃ„Â± parÃƒÂ§alara bÃƒÂ¶l (1500 karakter limiti)
        chunks = _split_message_into_chunks(message_body, max_chunk_length=1500)
        
        logger.debug(f"[Ã°Å¸â€â€] OpenAI API ÃƒÂ§aÃ„Å¸rÃ„Â±sÃ„Â± yapÃ„Â±lÃ„Â±yor (model: {model_name})...")
        logger.debug(f"[DEBUG] Mesaj uzunluÃ„Å¸u: {len(message_body)} karakter, {len(chunks)} parÃƒÂ§aya bÃƒÂ¶lÃƒÂ¼ndÃƒÂ¼")
        
        all_shipments = []
        
        # Her parÃƒÂ§ayÃ„Â± ayrÃ„Â± ayrÃ„Â± iÃ…Å¸le
        for idx, chunk in enumerate(chunks):
            if len(chunks) > 1:
                logger.debug(f"[Ã°Å¸â€œÂ¦] ParÃƒÂ§a {idx + 1}/{len(chunks)} iÃ…Å¸leniyor ({len(chunk)} karakter)...")
            
            try:
                chunk_shipments = _process_single_chunk(
                    chunk, message_id, client, location_matcher, valid_iller, iller_listesi, model_name
                )
                
                if chunk_shipments:
                    all_shipments.extend(chunk_shipments)
                    if len(chunks) > 1:
                        logger.debug(f"[Ã¢Å“â€œ] ParÃƒÂ§a {idx + 1}'den {len(chunk_shipments)} sevkiyat bulundu")
            except Exception as chunk_error:
                error_str = str(chunk_error)
                # Rate limit hatasÃ„Â± kontrolÃƒÂ¼
                if 'RATE_LIMIT_ERROR' in error_str or '429' in error_str or 'rate_limit' in error_str.lower():
                    logger.debug(f"[Ã¢Å¡ Ã¯Â¸Â] Rate limit hatasÃ„Â± tespit edildi: {error_str}")
                    logger.debug(f"[Ã¢â€Â¹Ã¯Â¸Â] Rate limit hatasÃ„Â± durumunda API key rotasyonu yapÃ„Â±labilir (config_api_key.py'de OPENAI_API_KEYS listesi)")
                    # TODO: API key rotasyonu eklenebilir
                else:
                    logger.error(f"[Ã¢Å¡ Ã¯Â¸Â] ParÃƒÂ§a {idx + 1} iÃ…Å¸lenirken hata: {chunk_error}")
        
        shipments_data = all_shipments
        
        if not shipments_data:
            logger.debug(f"[Ã¢Å¡ Ã¯Â¸Â] HiÃƒÂ§ sevkiyat bulunamadÃ„Â±")
            fallback_shipments = _fallback_parse_simple_routes(message_body, message_id, location_matcher)
            if fallback_shipments:
                shipments_data = fallback_shipments
            else:
                return []
        
        logger.debug(f"[Ã¢Å“â€œ] Toplam {len(shipments_data)} sevkiyat bulundu")
        
        # shipments_data zaten parse edilmiÃ…Å¸ olarak geliyor
        if not isinstance(shipments_data, list):
            shipments_data = [shipments_data] if shipments_data else []
        
        if not shipments_data:
            logger.debug(f"[Ã¢Å¡ Ã¯Â¸Â] OpenAI'den sevkiyat ÃƒÂ§Ã„Â±karÃ„Â±lamadÃ„Â±: {message_id}")
            return []
        
        try:
            validated_shipments = []
            for sh_data in shipments_data:
                try:
                    # None deÃ„Å¸erlerini temizle ve varsayÃ„Â±lan deÃ„Å¸erlere ÃƒÂ§evir
                    # String alanlar iÃƒÂ§in None -> ""
                    string_fields = ['isim', 'nereden_il', 'nereden_ilce', 'nereye_il', 'nereye_ilce', 
                                   'fiyat', 'telefon', 'aciklama', 'message_id']
                    for field in string_fields:
                        if field in sh_data and sh_data[field] is None:
                            sh_data[field] = ""
                        elif field not in sh_data:
                            if field == 'message_id':
                                sh_data[field] = message_id
                            else:
                                sh_data[field] = ""
                    
                    # List alanlar iÃƒÂ§in None -> []
                    list_fields = ['arac_tipi', 'kasa_tipi', 'yuk_tipi']
                    for field in list_fields:
                        if field in sh_data and sh_data[field] is None:
                            sh_data[field] = []
                        elif field not in sh_data:
                            sh_data[field] = []
                    
                    # Tip alanlarÃ„Â±nÃ„Â± liste olarak parse et
                    for tip_field in ['arac_tipi', 'kasa_tipi', 'yuk_tipi']:
                        if tip_field in sh_data:
                            tip_value = sh_data[tip_field]
                            if isinstance(tip_value, str):
                                if '+' in tip_value:
                                    sh_data[tip_field] = [v.strip() for v in tip_value.split('+') if v.strip()]
                                elif ',' in tip_value:
                                    sh_data[tip_field] = [v.strip() for v in tip_value.split(',') if v.strip()]
                                else:
                                    sh_data[tip_field] = [tip_value.strip()] if tip_value.strip() else []
                            elif not isinstance(tip_value, list):
                                sh_data[tip_field] = [str(tip_value).strip()] if tip_value else []
                            # EÃ„Å¸er boÃ…Å¸ liste ise varsayÃ„Â±lan deÃ„Å¸erleri kullan
                            if not sh_data[tip_field]:
                                if tip_field == 'arac_tipi':
                                    sh_data[tip_field] = ['1360']
                                elif tip_field == 'kasa_tipi':
                                    sh_data[tip_field] = ['AÃƒâ€¡IK', 'KAPALI']
                                elif tip_field == 'yuk_tipi':
                                    sh_data[tip_field] = ['KOMPLE']
                    
                    # message_id'yi garantile
                    if 'message_id' not in sh_data or not sh_data['message_id']:
                        sh_data['message_id'] = message_id
                    
                    shipment = Shipment(**sh_data)
                    sh_dict = shipment.model_dump()
                    
                    nereden_il = sh_dict.get('nereden_il', '')
                    nereden_ilce = sh_dict.get('nereden_ilce', '')
                    nereden_fixed = location_matcher.validate_and_fix(
                        nereden_il,
                        nereden_ilce,
                        message_body
                    )
                    
                    nereye_il = sh_dict.get('nereye_il', '')
                    nereye_ilce = sh_dict.get('nereye_ilce', '')
                    nereye_fixed = location_matcher.validate_and_fix(
                        nereye_il,
                        nereye_ilce,
                        message_body
                    )
                    
                    sh_dict['nereden_il'] = nereden_fixed['il']
                    sh_dict['nereden_ilce'] = nereden_fixed['ilce']
                    sh_dict['nereye_il'] = nereye_fixed['il']
                    sh_dict['nereye_ilce'] = nereye_fixed['ilce']
                    
                    if not sh_dict['nereden_il'] or not sh_dict['nereye_il']:
                        logger.debug(f"[Ã¢Å¡ Ã¯Â¸Â] GeÃƒÂ§ersiz sevkiyat atlandÃ„Â± (il bilgisi eksik): {message_id}")
                        continue
                    
                    if not sh_dict['nereden_ilce']:
                        matched_il = location_matcher._fuzzy_match_il(sh_dict['nereden_il'])
                        if matched_il and matched_il in location_matcher.il_to_default_original:
                            sh_dict['nereden_ilce'] = location_matcher.il_to_default_original[matched_il]
                    
                    if not sh_dict['nereye_ilce']:
                        matched_il = location_matcher._fuzzy_match_il(sh_dict['nereye_il'])
                        if matched_il and matched_il in location_matcher.il_to_default_original:
                            sh_dict['nereye_ilce'] = location_matcher.il_to_default_original[matched_il]
                    
                    validated_shipments.append(sh_dict)
                    
                except Exception as e:
                    logger.debug(f"[Ã¢Å¡ Ã¯Â¸Â] Sevkiyat validasyon hatasÃ„Â±: {e}")
                    continue
            
            return validated_shipments
            
        except Exception as e:
            logger.debug(f"[Ã¢ÂÅ’] Sevkiyat iÃ…Å¸leme hatasÃ„Â±: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    except Exception as e:
        logger.debug(f"[Ã¢ÂÅ’] OpenAI API hatasÃ„Â±: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_improved_parser():
    """SatÄ±r bazlÄ± tip tespiti iÃ§in basit bir regresyon testi Ã§alÄ±ÅŸtÄ±r."""
    sample_message = """AraÃ§lar aÃ§Ä±k veya kapalÄ± 13.60
05437327272
ElazÄ±ÄŸ dan Ä°stanbul Tuzla
ElazÄ±ÄŸ dan Mardin Nusaybin KAPALI 13.60"""


# ====================================================================================
# STUB FUNCTIONS FOR COMPATIBILITY (veri_cekici_ayristirici imports these)
# ====================================================================================

def load_unprocessed(queue_file=None):
    """Load unprocessed messages from queue file.

    Returns a list of message dicts.
    """
    qf = queue_file or os.path.join(os.path.dirname(__file__), '..', 'islenmemis_mesajlar.json')
    try:
        if os.path.exists(qf):
            with open(qf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and 'messages' in data:
                    return data['messages']
    except Exception:
        pass
    return []


def load_full_data_from_file(message_file=None):
    """Load full message data from file and return a dict of message bodies.

    Returns: {'message_bodies': {message_id: body, ...}}
    """
    mf = message_file or os.path.join(os.path.dirname(__file__), '..', 'mesajlar.json')
    result = {'message_bodies': {}}
    try:
        if os.path.exists(mf):
            with open(mf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                msgs = data.get('messages') if isinstance(data, dict) else data
                if isinstance(msgs, list):
                    for m in msgs:
                        mid = m.get('id')
                        body = m.get('body') or (m.get('raw_data', {}).get('text', {}).get('body') if isinstance(m.get('raw_data'), dict) else None)
                        if mid and body:
                            result['message_bodies'][mid] = body
    except Exception:
        pass
    return result


def sync_messages_to_unprocessed_queue(message_file=None, queue_file=None):
    """Sync messages from main message file to queue file.

    Copies unprocessed messages from `mesajlar.json` into `islenmemis_mesajlar.json`.
    """
    mf = message_file or os.path.join(os.path.dirname(__file__), '..', 'mesajlar.json')
    qf = queue_file or os.path.join(os.path.dirname(__file__), '..', 'islenmemis_mesajlar.json')
    try:
        msgs = []
        if os.path.exists(mf):
            with open(mf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                msgs = data.get('messages') if isinstance(data, dict) else data
        if not isinstance(msgs, list):
            return

        existing = []
        if os.path.exists(qf):
            try:
                with open(qf, 'r', encoding='utf-8') as fq:
                    existing = json.load(fq)
            except Exception:
                existing = []

        existing_ids = {e.get('id') for e in existing if isinstance(e, dict) and e.get('id')}

        appended = 0
        for m in msgs:
            if not isinstance(m, dict):
                continue
            mid = m.get('id')
            if not mid or mid in existing_ids:
                continue
            if m.get('is_processed'):
                continue
            entry = {
                'id': mid,
                'timestamp_readable': m.get('timestamp_readable') or m.get('parse_timestamp') or '',
                'sender_name': m.get('sender_name') or (m.get('raw_data', {}).get('from_name') if isinstance(m.get('raw_data'), dict) else ''),
                'chat_id': m.get('chat_id') or (m.get('raw_data', {}).get('chat_id') if isinstance(m.get('raw_data'), dict) else ''),
                'body': m.get('body') or (m.get('raw_data', {}).get('text', {}).get('body') if isinstance(m.get('raw_data'), dict) else '')
            }
            existing.append(entry)
            existing_ids.add(mid)
            appended += 1

        with open(qf, 'w', encoding='utf-8') as fq:
            json.dump(existing, fq, ensure_ascii=False, indent=2)

        if appended:
            logger.debug(f"[INFO] {appended} yeni mesaj kuyruÄŸa eklendi")
    except Exception as e:
        logger.error(f"[ERROR] sync_messages_to_unprocessed_queue hata: {e}")


def remove_unprocessed(message_id, queue_file=None):
    qf = queue_file or os.path.join(os.path.dirname(__file__), '..', 'islenmemis_mesajlar.json')
    try:
        if not os.path.exists(qf):
            return
        with open(qf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, list):
            return
        new = [m for m in data if not (isinstance(m, dict) and m.get('id') == message_id)]
        with open(qf, 'w', encoding='utf-8') as f:
            json.dump(new, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def remove_message_from_main_file(message_id, message_file=None):
    mf = message_file or os.path.join(os.path.dirname(__file__), '..', 'mesajlar.json')
    try:
        if not os.path.exists(mf):
            return
        with open(mf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        msgs = data.get('messages') if isinstance(data, dict) else data
        modified = False
        if isinstance(msgs, list):
            for m in msgs:
                if m.get('id') == message_id:
                    m['is_processed'] = True
                    modified = True
                    break
        if modified:
            if isinstance(data, dict):
                data['messages'] = msgs
                with open(mf, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                with open(mf, 'w', encoding='utf-8') as f:
                    json.dump(msgs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def main_listener():
    # No-op placeholder. Production integration should implement a listener that
    # updates `mesajlar.json` and/or the queue file.
    return



