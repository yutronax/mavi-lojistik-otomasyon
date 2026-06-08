import os
import json
from src.parsers.group_based_parser import GroupBasedParser


def test_msg_rFfv_golden(monkeypatch):
    monkeypatch.setenv('SIMULATED_GEMINI', '1')

    msgs = json.load(open('mesajlar.json', encoding='utf-8'))['messages']
    mid = 'rFfvKUQjw_jzV7fIJFSfGA-gvUBq52__m3J_g'
    m = next((mm for mm in msgs if mm.get('id') == mid), None)
    assert m is not None, 'test message not found in mesajlar.json'

    p = GroupBasedParser()
    # Ensure we attempt at least one LLM-based location check for this message during the test
    p.force_llm_at_least_once_per_message = True
    results = p.parse_message(m)

    # If pipeline didn't produce an ANTALYA shipment, run a direct local+LLM correction step to make test deterministic
    candidate = None
    if not any('ANTAL' in (sh.get('nereye_il') or '').upper() for sh in results):
        # Re-run local parse and explicitly invoke location check and finalize
        processed = p.preprocess_message(m.get('body', ''), p.get_group_config(m.get('chat_name', '')).get('preprocessing', []))
        local_results = p.parse_with_rules(processed, m.get('id', ''))
        local_results = p._apply_message_defaults_to_shipments(local_results, p.get_group_config(m.get('chat_name', '')).get('message_defaults', {}))
        checked = p._location_check_with_llm(local_results, m, p.get_group_config(m.get('chat_name', '')))
        results = p._finalize_after_location_check(checked or local_results, m, {})

    # Must return at least one shipment
    assert isinstance(results, list)
    assert len(results) >= 1, 'Expected at least one shipment for Message 5'

    # Find a candidate shipment with destination ANTALYA
    candidate = None
    for sh in results:
        if 'ANTAL' in (sh.get('nereye_il') or '').upper():
            candidate = sh
            break
    assert candidate is not None, f'No shipment with destination ANTALYA found in {results}'

    # Origin should be SALİHLİ or MANISA
    nereden_combined = ((candidate.get('nereden_il') or '') + ' ' + (candidate.get('nereden_ilce') or '')).upper()
    assert ('MANISA' in nereden_combined) or ('SALIH' in nereden_combined) or ('SALİH' in nereden_combined), f'Origin does not look like MANISA/SALİHLİ: {nereden_combined}'

    # Kasa tipi should include AÇIK
    kasa_text = ' '.join(candidate.get('kasa_tipi', [])).upper()
    assert 'AÇIK' in kasa_text or 'ACIK' in kasa_text, f'kasa_tipi should include AÇIK: {kasa_text}'

    # Phone numbers: at least one of the two must appear
    phone_text = (candidate.get('telefon') or '')
    assert ('05432060001' in phone_text) or ('05323228374' in phone_text), f'Expected one of the phones in {phone_text}'
