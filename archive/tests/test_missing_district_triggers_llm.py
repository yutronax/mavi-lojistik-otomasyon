import pytest
from src.parsers.group_based_parser import GroupBasedParser


def test_missing_district_triggers_and_fills(monkeypatch):
    gp = GroupBasedParser()
    # Simulate rule-based local parse returning a shipment with missing destination district
    local_results = [{'nereden_il': 'KAYSERİ', 'nereden_ilce': 'Kocasinan', 'nereye_il': 'İZMİR', 'nereye_ilce': ''}]

    monkeypatch.setattr(GroupBasedParser, 'parse_with_rules', lambda self, msg, mid: local_results)

    called = {}

    def fake_loc_check(self, shipments, message, config, reason=None):
        called['reason'] = reason
        # Fill missing district
        for sh in shipments:
            if sh.get('nereye_il') and not sh.get('nereye_ilce'):
                sh['nereye_ilce'] = 'KARABAĞLAR'
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check)

    res = gp.parse_with_openai('KAYSERİ➡️İZMİR', 'mid', {'parser_type': 'rule_based'})
    assert called.get('reason') == 'missing_district'
    assert res and res[0]['nereye_ilce'] == 'KARABAĞLAR'


