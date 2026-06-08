import json
import pytest
from src.parsers.group_based_parser import GroupBasedParser


# Reusable fake that records calls
CALL_INFO = {}

def fake_generate_content_text(api_key, model, full_prompt, response_mime_type='application/json', **kwargs):
    CALL_INFO['model'] = model
    CALL_INFO.setdefault('calls', 0)
    CALL_INFO['calls'] += 1
    # Generic fallback: return an empty shipments array
    return json.dumps({"shipments": []}, ensure_ascii=False)


def test_multi_dest_flash(monkeypatch):
    """Multi-destination messages should be split into separate shipments and cleaned."""
    monkeypatch.setenv('LLM_COST_MODE', 'flash')
    # LLM returns two shipments; one with noisy nereye_ilce containing digits, other with price '13.60'
    def fake_multi(api_key, model, full_prompt, **kwargs):
        CALL_INFO['model'] = model
        resp = {
            "shipments": [
                {"isim": "", "nereden_il": "ANKARA", "nereden_ilce": "MERKEZ", "nereye_il": "İZMİR", "nereye_ilce": "Karabağlar 13-60", "arac_tipi": ["1360"], "kasa_tipi": ["AÇIK"], "yuk_tipi": ["KOMPLE"], "fiyat": "26000+KDV", "message_id": "m1"},
                {"isim": "", "nereden_il": "ANKARA", "nereden_ilce": "MERKEZ", "nereye_il": "BURSA", "nereye_ilce": "1 palet", "arac_tipi": [], "kasa_tipi": [], "yuk_tipi": ["PALET"], "fiyat": "13.60", "message_id": "m1"}
            ]
        }
        return json.dumps(resp, ensure_ascii=False)

    monkeypatch.setattr('src.utils.gemini_adapter.generate_content_text', fake_multi)
    # patch location check to behave as mini LLM correction (sanitize districts)
    def fake_loc_check(self, shipments, message, config, reason=None):
        for sh in shipments:
            if sh.get('nereye_ilce'):
                sh['nereye_ilce'] = ''.join([c for c in sh['nereye_ilce'] if not c.isdigit()]).strip()
                # If becomes empty or contains cargo words, set MERKEZ
                cleaned = sh['nereye_ilce'].upper()
                if not cleaned or any(tok in cleaned for tok in ['PALET','PAL','SÜNGER','YÜKÜSTÜ']):
                    sh['nereye_ilce'] = 'MERKEZ'
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check)

    gp = GroupBasedParser()
    # Mark as BİM-like message so price tokens (13.60) are handled by special rules
    msg = "ANKARA → İZMİR, BURSA BİM"
    parsed = gp.parse_message({'body': msg, 'id': 'm1', 'chat_name': 'MULTI TEST'})

    assert len(parsed) == 2
    # Ensure model was flash
    assert CALL_INFO.get('model') == 'gemini-2.5-flash'
    # First destination district cleaned (no digits)
    im_sh = [s for s in parsed if s.get('nereye_il') == 'İZMİR'][0]
    assert '13-60' not in (im_sh.get('nereye_ilce') or '')
    # Second destination: price '13.60' should be normalized to fiyat='SORUNUZ' and also added to arac_tipi or kasa_tipi
    br_sh = [s for s in parsed if s.get('nereye_il') == 'BURSA'][0]
    assert br_sh.get('fiyat') == 'SORUNUZ'


def test_list_flash(monkeypatch):
    """List format messages (emoji / bullets) parse into per-line shipments and scrub districts."""
    monkeypatch.setenv('LLM_COST_MODE', 'flash')

    def fake_list(api_key, model, full_prompt, **kwargs):
        CALL_INFO['model'] = model
        resp = {
            "shipments": [
                {"isim": "", "nereden_il": "İZMİR", "nereden_ilce": "MERKEZ", "nereye_il": "KAYSERİ", "nereye_ilce": "Kocasinan 1", "arac_tipi": [], "kasa_tipi": [], "yuk_tipi": ["PARÇA"], "fiyat": "SORUNUZ", "message_id": "l1"},
                {"isim": "", "nereden_il": "İZMİR", "nereden_ilce": "MERKEZ", "nereye_il": "MANİSA", "nereye_ilce": "2 palet", "arac_tipi": [], "kasa_tipi": [], "yuk_tipi": ["PALET"], "fiyat": "13.60", "message_id": "l1"}
            ]
        }
        return json.dumps(resp, ensure_ascii=False)

    monkeypatch.setattr('src.utils.gemini_adapter.generate_content_text', fake_list)

    def fake_loc_check(self, shipments, message, config, reason=None):
        for sh in shipments:
            if sh.get('nereye_ilce'):
                cleaned = ''.join([c for c in sh['nereye_ilce'] if not c.isdigit()]).strip()
                if not cleaned or any(tok in cleaned.upper() for tok in ['PALET','PAL']):
                    sh['nereye_ilce'] = 'MERKEZ'
                else:
                    sh['nereye_ilce'] = cleaned
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check)

    gp = GroupBasedParser()
    msg = "🚛 İZMİR → KAYSERİ Kocasinan 1\n🚛 İZMİR → MANİSA 2 palet"
    parsed = gp.parse_message({'body': msg, 'id': 'l1', 'chat_name': 'LIST TEST'})

    assert len(parsed) == 2
    assert CALL_INFO.get('model') == 'gemini-2.5-flash'
    for sh in parsed:
        assert not any(ch.isdigit() for ch in (sh.get('nereye_ilce') or ''))


def test_key_value_flash(monkeypatch):
    """Key:value format messages should map fields and be cleaned properly."""
    monkeypatch.setenv('LLM_COST_MODE', 'flash')

    def fake_kv(api_key, model, full_prompt, **kwargs):
        CALL_INFO['model'] = model
        resp = {
            "shipments": [
                {"isim": "", "nereden_il": "ANTALYA", "nereden_ilce": "MERKEZ", "nereye_il": "İZMİR", "nereye_ilce": "Konak 13-60", "arac_tipi": [], "kasa_tipi": [], "yuk_tipi": ["KOMPLE"], "fiyat": "13.60", "message_id": "kv1"}
            ]
        }
        return json.dumps(resp, ensure_ascii=False)

    monkeypatch.setattr('src.utils.gemini_adapter.generate_content_text', fake_kv)

    def fake_loc_check(self, shipments, message, config, reason=None):
        for sh in shipments:
            if sh.get('nereye_ilce'):
                new = ''.join([c for c in sh['nereye_ilce'] if not c.isdigit()]).strip()
                if not new or any(tok in new.upper() for tok in ['PALET','PAL','13-60']):
                    sh['nereye_ilce'] = 'MERKEZ'
                else:
                    sh['nereye_ilce'] = new
            if sh.get('fiyat') and sh.get('fiyat').strip() == '13.60':
                # Move price into arac_tipi and normalize fiyat
                sh.setdefault('arac_tipi', [])
                if '13.60' not in sh['arac_tipi']:
                    sh['arac_tipi'].insert(0, '13.60')
                sh['fiyat'] = 'SORUNUZ'
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check)

    gp = GroupBasedParser()
    msg = "Yükleme Yeri: ANTALYA\nİndirme Yeri: İZMİR Konak 13-60\nFiyat: 13.60"
    parsed = gp.parse_message({'body': msg, 'id': 'kv1', 'chat_name': 'KV TEST'})

    assert len(parsed) == 1
    sh = parsed[0]
    # District must have no digits
    assert not any(ch.isdigit() for ch in (sh.get('nereye_ilce') or ''))
    # Price should be normalized to SORUNUZ and price token moved into a type field
    assert sh.get('fiyat') == 'SORUNUZ'
    assert (any('13.60' in (t or '') for t in (sh.get('arac_tipi') or [])) or any('13.60' in (t or '') for t in (sh.get('kasa_tipi') or [])))


def test_multi_dest_variations_and_overrides(monkeypatch):
    monkeypatch.setenv('LLM_COST_MODE', 'flash')

    def fake_multi2(api_key, model, full_prompt, **kwargs):
        # Multiple destinations separated by '+', 've', commas
        resp = {
            "shipments": [
                {"nereden_il": "ANTALYA", "nereden_ilce": "MERKEZ", "nereye_il": "İZMİR", "nereye_ilce": "Karabağlar", "fiyat": "26000+KDV", "message_id": "md1"},
                {"nereden_il": "ANTALYA", "nereden_ilce": "MERKEZ", "nereye_il": "BURSA", "nereye_ilce": "Osmangazi 1", "fiyat": "13.60", "message_id": "md1"},
                {"nereden_il": "ANTALYA", "nereden_ilce": "MERKEZ", "nereye_il": "KONYA", "nereye_ilce": "MERKEZ", "fiyat": "SORUNUZ", "message_id": "md1"}
            ]
        }
        return json.dumps(resp, ensure_ascii=False)

    monkeypatch.setattr('src.utils.gemini_adapter.generate_content_text', fake_multi2)

    def fake_loc_check2(self, shipments, message, config, reason=None):
        for sh in shipments:
            if sh.get('nereye_ilce'):
                cleaned = ''.join([c for c in sh['nereye_ilce'] if not c.isdigit()]).strip()
                if not cleaned or any(tok in cleaned.upper() for tok in ['PALET','PAL']):
                    sh['nereye_ilce'] = 'MERKEZ'
                else:
                    sh['nereye_ilce'] = cleaned
            if sh.get('fiyat') and sh['fiyat'] == '13.60':
                sh.setdefault('arac_tipi', [])
                sh['arac_tipi'].insert(0, '13.60')
                sh['fiyat'] = 'SORUNUZ'
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check2)

    gp = GroupBasedParser()
    msg = "ANTALYA → İZMİR + BURSA ve KONYA"
    parsed = gp.parse_message({'body': msg, 'id': 'md1', 'chat_name': 'MULTI VAR TEST'})

    assert len(parsed) == 3
    # Ensure the BURSA entry had price normalized
    br = [s for s in parsed if s.get('nereye_il') == 'BURSA'][0]
    assert br.get('fiyat') == 'SORUNUZ'
    assert any('13.60' in (t or '') for t in (br.get('arac_tipi') or []))


def test_key_value_missing_fields_and_mixed_lang(monkeypatch):
    monkeypatch.setenv('LLM_COST_MODE', 'flash')

    def fake_kv2(api_key, model, full_prompt, **kwargs):
        resp = {
            "shipments": [
                {"nereden_il": "ISTANBUL", "nereden_ilce": "", "nereye_il": "KAYSERI", "nereye_ilce": "1 palet", "fiyat": "13.60", "message_id": "kv2"}
            ]
        }
        return json.dumps(resp, ensure_ascii=False)

    monkeypatch.setattr('src.utils.gemini_adapter.generate_content_text', fake_kv2)

    def fake_loc_check3(self, shipments, message, config, reason=None):
        for sh in shipments:
            # If origin district missing, fill with MERKEZ
            if not sh.get('nereden_ilce'):
                sh['nereden_ilce'] = 'MERKEZ'
            # Sanitize destination ilce
            if sh.get('nereye_ilce'):
                cleaned = ''.join([c for c in sh['nereye_ilce'] if not c.isdigit()]).strip()
                if not cleaned or any(tok in cleaned.upper() for tok in ['PALET','PAL']):
                    sh['nereye_ilce'] = 'MERKEZ'
                else:
                    sh['nereye_ilce'] = cleaned
            if sh.get('fiyat') and sh['fiyat'] == '13.60':
                sh.setdefault('arac_tipi', [])
                sh['arac_tipi'].insert(0, '13.60')
                sh['fiyat'] = 'SORUNUZ'
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check3)

    gp = GroupBasedParser()
    msg = "Load place: ISTANBUL\nDrop: KAYSERI 1 palet\nPrice: 13.60"
    parsed = gp.parse_message({'body': msg, 'id': 'kv2', 'chat_name': 'KV MIX TEST'})

    assert len(parsed) == 1
    sh = parsed[0]
    assert sh.get('nereden_ilce') == 'MERKEZ'
    assert sh.get('nereye_ilce') == 'MERKEZ'
    assert sh.get('fiyat') == 'SORUNUZ'
    assert any('13.60' in (t or '') for t in (sh.get('arac_tipi') or []))
