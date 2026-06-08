import json
import re
import pytest
from src.parsers.group_based_parser import GroupBasedParser

MERSIN_MSG = """
MERSİN —ANKARA TIR KAPALI 26 TON (3 TIR LAZIM)
MERSIN — ADANA 10 TEKER 15 TON
ADANA—ÇANAKKALE 5 PALET 4 TON
ADANA — TOKAT TURHAL 2 PALET 2.500 KG
ADANA — BURSA PARCA 100 KG
"""


def test_mersin_ankara_complex_flow(monkeypatch, caplog):
    monkeypatch.setenv('LLM_COST_MODE', 'flash')
    # Ensure simulated gemini is used so both full parse and location-check call generate_content_text
    monkeypatch.setenv('SIMULATED_GEMINI', '1')

    def fake_generate(api_key, model, contents, **kwargs):
        # If it's a location_check prompt (contains 'Verify/correct'), return invalid JSON
        if 'Verify/correct' in (contents or ''):
            return 'INVALID NOT JSON'
        # Otherwise, return a sensible JSON for the five lines
        resp = {
            'shipments': [
                {'isim': '', 'nereden_il': 'MERSİN', 'nereden_ilce': 'MERKEZ', 'nereye_il': 'ANKARA', 'nereye_ilce': 'MERKEZ', 'arac_tipi': ['1360'], 'kasa_tipi': ['KAPALI'], 'yuk_tipi': ['DÖKME'], 'fiyat': 'SORUNUZ', 'aciklama': '26 TON (3 TIR LAZIM)', 'message_id': 'mersin1'},
                {'isim': '', 'nereden_il': 'MERSİN', 'nereden_ilce': 'MERKEZ', 'nereye_il': 'ADANA', 'nereye_ilce': 'MERKEZ', 'arac_tipi': ['1360'], 'kasa_tipi': ['KAPALI'], 'yuk_tipi': ['KOMPLE'], 'fiyat': 'SORUNUZ', 'aciklama': '10 TEKER 15 TON', 'message_id': 'mersin1'},
                {'isim': '', 'nereden_il': 'ADANA', 'nereden_ilce': 'MERKEZ', 'nereye_il': 'ÇANAKKALE', 'nereye_ilce': 'MERKEZ', 'arac_tipi': ['1360'], 'kasa_tipi': ['AÇIK'], 'yuk_tipi': ['PALET'], 'fiyat': 'SORUNUZ', 'aciklama': '5 PALET 4 TON', 'message_id': 'mersin1'},
                {'isim': '', 'nereden_il': 'ADANA', 'nereden_ilce': 'MERKEZ', 'nereye_il': 'TOKAT', 'nereye_ilce': 'TURHAL', 'arac_tipi': ['1360'], 'kasa_tipi': ['AÇIK'], 'yuk_tipi': ['PALET'], 'fiyat': 'SORUNUZ', 'aciklama': '2 PALET 2.500 KG', 'message_id': 'mersin1'},
                {'isim': '', 'nereden_il': 'ADANA', 'nereden_ilce': 'MERKEZ', 'nereye_il': 'BURSA', 'nereye_ilce': 'MERKEZ', 'arac_tipi': ['1360'], 'kasa_tipi': ['AÇIK'], 'yuk_tipi': ['PARÇA'], 'fiyat': 'SORUNUZ', 'aciklama': 'PARCA 100 KG', 'message_id': 'mersin1'},
            ]
        }
        return json.dumps(resp, ensure_ascii=False)

    monkeypatch.setattr('src.utils.gemini_adapter.generate_content_text', fake_generate)

    gp = GroupBasedParser()
    caplog.clear()
    caplog.set_level('INFO')

    results = gp.parse_message({'body': MERSIN_MSG, 'id': 'mersin1', 'chat_name': 'MERSIN TEST'})

    # Expect 5 shipments
    assert len(results) == 5

    # No empty destination province or district
    for sh in results:
        assert sh.get('nereye_il'), f"Missing nereye_il in {sh}"
        assert sh.get('nereye_ilce') is not None
        # district should not contain digits or cargo tokens
        assert not re.search(r'\d', sh.get('nereye_ilce') or ''), f"District contains digits: {sh.get('nereye_ilce')}"
        assert 'PAL' not in (sh.get('nereye_ilce') or '').upper()
        # fiyat should not be raw ton tokens
        assert 'TON' not in (sh.get('fiyat') or '').upper()

    # Ensure that location_check JSON parse failure was logged but did not crash parser
    assert any('event=llm_location_check_parse_failed' in rec.getMessage() or 'llm_location_check_parse_failed' in rec.getMessage() for rec in caplog.records)

    # Ensure we did not attempt V2 fallback (no V2 Parser log)
    assert not any('V2 Parser' in rec.getMessage() for rec in caplog.records)

    # Ensure meaningful shipment data returned
    ids = [s['nereye_il'] for s in results]
    assert set(['ANKARA', 'ADANA', 'ÇANAKKALE', 'TOKAT', 'BURSA']).issubset(set([i.upper() for i in ids]))
