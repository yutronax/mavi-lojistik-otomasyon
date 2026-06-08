import json
import logging
import pytest
from src.parsers.group_based_parser import GroupBasedParser


def test_llm_attempted_when_flag_on(monkeypatch, caplog):
    caplog.set_level(logging.INFO)

    def fake_config(self, group_name):
        return {'parser_type': 'rule_based', 'fallback_to_openai': False, 'preprocessing': ['split_lines']}

    monkeypatch.setattr(GroupBasedParser, 'get_group_config', fake_config)

    gp = GroupBasedParser(force_llm_at_least_once_per_message=True)

    # Use a message that rule-based parsing will catch
    msg = {'body': 'ANKARA -> IZMIR', 'id': 'm1', 'chat_name': 'TEST'}

    # Ensure no client present so the helper will skip external call but still increment attempts
    gp.client = None

    gp.parse_message(msg)

    assert gp.llm_attempts >= 1
    assert any('event=llm_location_check' in r.message or 'llm_location_check' in r.message for r in caplog.records)


def test_llm_applies_corrections_via_hook(monkeypatch):
    def fake_config(self, group_name):
        return {'parser_type': 'rule_based', 'fallback_to_openai': False, 'preprocessing': ['split_lines']}

    monkeypatch.setattr(GroupBasedParser, 'get_group_config', fake_config)

    gp = GroupBasedParser(force_llm_at_least_once_per_message=True)

    # Monkeypatch the location check to simulate a correction for index 0
    def fake_location_check(self, shipments, message, config):
        shipments[0]['nereden_il'] = 'ANKARA'
        shipments[0]['nereden_ilce'] = 'MERKEZ'
        # Also ensure destination exists to avoid final drop in new finalization rules
        shipments[0]['nereye_il'] = shipments[0].get('nereye_il') or 'İZMİR'
        shipments[0]['nereye_ilce'] = shipments[0].get('nereye_ilce') or 'MERKEZ'
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_location_check)

    msg = {'body': '-> IZMIR', 'id': 'm2', 'chat_name': 'TEST-TYPES'}
    # parse_message will create a shipment; ensure correction applied
    results = gp.parse_message(msg)
    assert results
    assert any(r.get('nereden_il') == 'ANKARA' or r.get('nereden_ilce') == 'MERKEZ' for r in results)


import os

def test_llm_calls_client_with_mini_model(monkeypatch):
    gp = GroupBasedParser()

    called = {}

    class FakeResp:
        def __init__(self, text):
            self.choices = [type('C', (), {'message': type('M', (), {'content': text})})]

    class FakeChat:
        def completions(self, *args, **kwargs):
            pass
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                called['kwargs'] = kwargs
                # Return an empty correction list
                return FakeResp('[]')

    class FakeClient:
        chat = FakeChat()

    gp.client = FakeClient()

    shipments = [{'nereden_il': '', 'nereden_ilce': '', 'nereye_il': 'İZMİR', 'nereye_ilce': ''}]
    gp._location_check_with_llm(shipments, 'dummy', {})

    # If tests run in simulated Gemini mode the function won't call the client; in that case ensure we didn't record kwargs
    if os.getenv('SIMULATED_GEMINI', '0') == '1':
        assert called == {}
        return

    assert 'kwargs' in called
    assert 'model' in called['kwargs']
    assert 'gemini' in called['kwargs']['model'] or 'mini' in called['kwargs']['model']
    assert called['kwargs'].get('max_tokens', 0) <= 300
