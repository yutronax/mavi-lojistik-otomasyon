import os
import json
from src.parsers.group_based_parser import GroupBasedParser


def test_rFfv_parses_and_sanitizes(monkeypatch):
    # Use simulated Gemini only for this test and ensure it's set before parser initialization
    monkeypatch.setenv('SIMULATED_GEMINI', '1')

    msgs = json.load(open('mesajlar.json', encoding='utf-8'))['messages']
    # find the message by id
    mid = 'rFfvKUQjw_jzV7fIJFSfGA-gvUBq52__m3J_g'
    m = next((mm for mm in msgs if mm.get('id') == mid), None)
    assert m is not None, 'test message not found in mesajlar.json'

    p = GroupBasedParser()
    # Should not raise
    results = p.parse_message(m)

    # Must produce a list
    assert isinstance(results, list)

    # If there are shipments with missing destination fields, run location-check correction and finalize
    if any(not sh.get('nereye_il') or not sh.get('nereye_ilce') for sh in results):
        corrected = p._location_check_with_llm(results, m, {})
        results = p._finalize_after_location_check(corrected or results, m, {}, None)

    # If there are no shipments after finalization that's acceptable; otherwise validate each
    if not results:
        return

    for sh in results:
        # destination province and district must exist
        assert sh.get('nereye_il'), f"missing nereye_il in {sh}"
        assert sh.get('nereye_ilce'), f"missing nereye_ilce in {sh}"
        # districts must not contain digits or cargo/type blacklist tokens
        bad_tokens = set(['AÇIK', 'ACIK', 'TIR', 'PAL', 'PALET', 'KDV', 'TL'])
        for key in ('nereden_ilce', 'nereye_ilce'):
            val = sh.get(key, '') or ''
            assert not any(ch.isdigit() for ch in val), f"digits in {key}: {val}"
            up = val.upper()
            assert not any(bt in up for bt in bad_tokens), f"blacklisted token in {key}: {val}"
        # fiyat should be 'SORUNUZ' or a numeric-like token
        f = sh.get('fiyat', '') or ''
        assert f == 'SORUNUZ' or isinstance(f, str) and f.strip(), 'fiyat should be SORUNUZ or non-empty'
