import os
import json
import pytest
from src.parsers.group_based_parser import GroupBasedParser

KAYSERI_MSG = """
KAYSERİ → İZMİR Karabağlar 13-60 AÇIK TIR sünger 26.000+KDV
KAYSERİ → BİM ARNAVUTKÖY 13.60
"""


CALL_INFO = {}

def fake_generate_content_text(api_key, model, full_prompt, response_mime_type='application/json', **kwargs):
    # record call for assertions
    CALL_INFO['model'] = model
    CALL_INFO['prompt'] = full_prompt
    # Return a mock JSON that simulates a helpful Flash model output
    # Include a BİM-like line with price 13.60 to trigger BİM rules
    resp = {
        "shipments": [
            {
                "isim": "",
                "nereden_il": "KAYSERİ",
                "nereden_ilce": "MERKEZ",
                "nereye_il": "İZMİR",
                "nereye_ilce": "Karabağlar",
                "arac_tipi": ["1360"],
                "kasa_tipi": ["AÇIK"],
                "yuk_tipi": ["KOMPLE"],
                "fiyat": "26000+KDV",
                "telefon": "",
                "aciklama": "sünger",
                "message_id": "kayseri_1"
            },
            {
                "isim": "",
                "nereden_il": "KAYSERİ",
                "nereden_ilce": "MERKEZ",
                "nereye_il": "İSTANBUL",
                "nereye_ilce": "ARNAVUTKÖY",
                "arac_tipi": [],
                "kasa_tipi": [],
                "yuk_tipi": ["KOMPLE"],
                "fiyat": "13.60",
                "telefon": "",
                "aciklama": "BİM gönderisi",
                "message_id": "kayseri_1"
            }
        ]
    }
    return json.dumps(resp, ensure_ascii=False)


def test_flash_full_parse_kayseri_bim(monkeypatch):
    # Force Flash LLM-first mode
    monkeypatch.setenv('LLM_COST_MODE', 'flash')

    # Patch the Gemini helper to return a deterministic JSON
    monkeypatch.setattr('src.utils.gemini_adapter.generate_content_text', fake_generate_content_text)

    # Patch location check to be a light sanitizer (simulate mini LLM corrections)
    def fake_loc_check(self, shipments, message, config, reason=None):
        for sh in shipments:
            # sanitize nereye_ilce to title case and strip numeric tokens
            if sh.get('nereye_ilce'):
                sh['nereye_ilce'] = ''.join([c for c in sh['nereye_ilce'] if not c.isdigit()]).strip().title()
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check)

    gp = GroupBasedParser()

    parsed = gp.parse_message({'body': KAYSERI_MSG, 'id': 'kayseri_1', 'chat_name': 'KAYSERI TEST'})

    # Expect both shipments present
    assert len(parsed) == 2

    # Ensure our generate_content_text was called with flash model
    assert CALL_INFO.get('model') == 'gemini-2.5-flash'

    # BİM-specific expectations: price '13.60' should be turned into an arac_tipi token and fiyat set to 'SORUNUZ'
    bim_sh = [s for s in parsed if 'ARNAVUTKÖY' in (s.get('nereye_ilce') or '').upper() or 'BIM' in (s.get('aciklama') or '').upper()]
    assert bim_sh, 'expected a BİM-like shipment'
    bim = bim_sh[0]
    # price moved to arac_tipi and fiyat normalized
    assert bim.get('fiyat') == 'SORUNUZ'
    assert any('13.60' in (t or '') for t in (bim.get('arac_tipi') or [])) or any('13.60' in (t or '') for t in (bim.get('kasa_tipi') or []))

    # District cleaned (no digits)
    for sh in parsed:
        assert not any(ch.isdigit() for ch in (sh.get('nereye_ilce') or ''))

