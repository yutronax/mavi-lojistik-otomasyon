import os
import json
from src.parsers.group_based_parser import GroupBasedParser


def test_structured_parse_and_validation_simulated(monkeypatch):
    # use simulated gemini for deterministic runs
    monkeypatch.setenv('SIMULATED_GEMINI', '1')
    parser = GroupBasedParser()
    msg = "İZMİR ➡️ ANKARA 13/60 - 1 ARAÇ\nİRTİBAT: 0537 000 00 00"
    results = parser.parse_with_openai(msg, 'test-mid', {'model': 'gemini-2.5-mini'})
    assert isinstance(results, list)
    # when simulated, expect some shipments or empty list but no exception
    # if shipments found, they should include message_id or be dicts
    for sh in results:
        assert isinstance(sh, dict)
