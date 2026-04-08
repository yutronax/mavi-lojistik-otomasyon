import os
import logging
import pytest

from src.parsers.advanced_shipment_parser import AdvancedShipmentParser
from src.parsers.group_based_parser import GroupBasedParser, logger as gb_logger


def test_agents_disabled_and_no_llm(monkeypatch, caplog):
    """When ENABLE_LOCATION_EXTRACTOR=0 and ENABLE_LOCATION_RESEARCH=0:
    - AdvancedShipmentParser must not instantiate LocationExtractorAgent
    - GroupBasedParser must not invoke LLM when rule-based parsing returns results
    """
    # Ensure env guards are OFF
    monkeypatch.setenv('ENABLE_LOCATION_EXTRACTOR', '0')
    monkeypatch.setenv('ENABLE_LOCATION_RESEARCH', '0')

    # Advanced parser should not instantiate extractor
    adv = AdvancedShipmentParser()
    assert adv.location_extractor is None

    # Ensure logs are captured and do not contain instantiation line
    caplog.set_level(logging.INFO)
    assert not any('LocationExtractorAgent instantiated' in r.message for r in caplog.records)

    # Prepare GroupBasedParser and force a rule-based config for test
    def fake_config(self, group_name):
        return {
            'parser_type': 'rule_based',
            'fallback_to_openai': False,
            'preprocessing': ['split_lines']
        }

    monkeypatch.setattr(GroupBasedParser, 'get_group_config', fake_config)

    gp = GroupBasedParser()

    # Use a message that is easy for rule-based parser to catch (simple route)
    msg = {'body': 'ANKARA -> IZMIR', 'id': 'm1', 'chat_name': 'TEST-GROUP'}

    caplog.clear()
    res = gp.parse_message(msg)

    # parse_message should not have tried to increment llm_attempts (no LLM consideration)
    assert gp.llm_attempts == 0

    # No logs indicating LLM invocation
    assert not any('invoking LLM' in r.message or 'Rule-based: invoking' in r.message or '[→] Rule-based' in r.message for r in caplog.records)


def test_line_level_type_override(monkeypatch):
    """Verify that explicit per-line types override message-level defaults"""
    # Force rule-based behavior for deterministic outputs
    def fake_config(self, group_name):
        return {
            'parser_type': 'rule_based',
            'fallback_to_openai': False,
            'preprocessing': ['split_lines']
        }

    monkeypatch.setattr(GroupBasedParser, 'get_group_config', fake_config)

    # Patch location resolution to avoid dependency on external il_ilçeler.json
    def fake_resolve(self, text: str):
        t = (text or '').upper()
        if 'ANKARA' in t and 'IZMIR' in t:
            # For combined lines this isn't used; our parser splits on arrows
            return None
        if 'ANKARA' in t:
            return {'il': 'ANKARA', 'ilce': 'MERKEZ'}
        if 'IZMIR' in t:
            return {'il': 'İZMIR', 'ilce': 'MERKEZ'}
        if 'BURSA' in t:
            return {'il': 'BURSA', 'ilce': 'MERKEZ'}
        if 'ADANA' in t:
            return {'il': 'ADANA', 'ilce': 'MERKEZ'}
        return None

    monkeypatch.setattr(GroupBasedParser, '_resolve_location', fake_resolve)

    gp = GroupBasedParser()

    # Message: first line declares global defaults; second line no types; third line has explicit types TENTE + DOKME
    body = """
    1360 TIR AÇIK KOMPLE
    ANKARA -> IZMIR
    BURSA -> ADANA TENTE DÖKME
    """

    msg = {'body': body, 'id': 'm2', 'chat_name': 'TEST-TYPES'}
    results = gp.parse_message(msg)

    # Find shipments by origin
    # We expect an ANKARA->IZMIR shipment that inherits global types
    ank_to_izm = [r for r in results if r.get('nereden_il') == 'ANKARA' and r.get('nereye_il') == 'İZMIR']
    assert ank_to_izm, f"Expected ANKARA->IZMIR shipment, got: {results}"
    ank = ank_to_izm[0]
    # Global line should propagate defaults to lines that do not have explicit types
    # We assert presence of global defaults (rather than strict equality) to be robust
    assert '1360' in ank['arac_tipi']
    assert 'AÇIK' in ank['kasa_tipi']
    assert 'KOMPLE' in ank['yuk_tipi']

    # For BURSA->ADANA the line contains explicit TENTE (kasa->KAPALI) and DÖKME (yuk->DÖKME)
    bur_to_ad = [r for r in results if r.get('nereden_il') == 'BURSA' and r.get('nereye_il') == 'ADANA']
    assert bur_to_ad, f"Expected BURSA->ADANA shipment, got: {results}"
    bur = bur_to_ad[0]
    # Explicit types must NOT include global defaults (no global 'KOMPLE' added)
    assert 'KOMPLE' not in bur['yuk_tipi']
    assert 'DÖKME' in bur['yuk_tipi']
    # Kasa type should reflect explicit 'TENTE' as KAPALI (at least include it)
    assert any('KAPALI' in k for k in bur['kasa_tipi'])


if __name__ == '__main__':
    pytest.main(['-q'])
