import pytest

from src.parsers.group_based_parser import GroupBasedParser

KAYSERI_MSG = """
KAYSERİ → İZMİR Karabağlar 13-60 AÇIK TIR sünger 26.000+KDV
KAYSERİ → HATAY Samandağ 13-60 AÇIK TIR yapıştırıcı+strapor 26.000+KDV
KAYSERİ → BURSA İnegöl yüküstü sünger metreküp 200 TL
KAYSERİ → MANİSA Turgutlu yüküstü
KAYSERİ → AĞRI yüküstü sünger
KAYSERİ → DİYARBAKIR yüküstü
KAYSERİ → İSTANBUL Pendik yüküstü
KAYSERİ → İSTANBUL Avcılar yüküstü
KAYSERİ → İZMİR Karabağlar yüküstü
KAYSERİ → KARAMAN 1 palet
"""


def fake_config(self, group_name):
    # Force this test group to use LLM-first
    return {'parser_type': 'openai', 'force_llm_first': True, 'llm_first_max_tokens': 600}


def test_kayseri_golden_llm_first(monkeypatch):
    monkeypatch.setattr(GroupBasedParser, 'get_group_config', fake_config)

    gp = GroupBasedParser()

    # Mock parse_with_openai to return reasonable structured shipments (simulating a helpful LLM)
    def fake_llm_parse(self, message, message_id, config):
        # Return a list of shipments per line
        shipments = []
        lines = [l.strip() for l in message.split('\n') if l.strip()]
        for i, ln in enumerate(lines):
            # naive: split origin -> rest
            parts = ln.split('→')
            origin = parts[0].strip()
            rest = parts[1].strip() if len(parts) > 1 else ''
            dest_parts = rest.split()
            nereye_il = dest_parts[0]
            nereye_ilce = ' '.join(dest_parts[1:3]) if len(dest_parts) > 1 else 'MERKEZ'
            shipments.append({'nereden_il': 'KAYSERİ', 'nereden_ilce': 'MERKEZ', 'nereye_il': nereye_il, 'nereye_ilce': nereye_ilce, 'aciklama': ln, 'arac_tipi': ['1360'], 'kasa_tipi': ['AÇIK'], 'yuk_tipi': ['KOMPLE']})
        return shipments

    monkeypatch.setattr(GroupBasedParser, 'parse_with_openai', fake_llm_parse)

    results = gp.parse_message({'body': KAYSERI_MSG, 'id': 'kayseri_1', 'chat_name': 'KAYSERI TEST'})
    assert results, "Expected parsed shipments"

    # Expect 10 shipments
    assert len(results) == 10

    # Check that no nereye_ilce contains garbage tokens like '13-60AÇIK' or 'YÜKÜSTÜ'
    for sh in results:
        ni = sh.get('nereye_ilce', '')
        assert '13-60' not in ni
        assert 'YÜKÜSTÜ' not in ni

    # Check at least one has '1 palet' in description but not in ilce
    palet = [s for s in results if 'KARAMAN' in (s.get('nereye_il') or '')]
    assert palet
    k = palet[0]
    assert '1 palet' in k.get('aciklama', '')
    assert k.get('nereye_ilce') == 'MERKEZ' or k.get('nereye_ilce') == ''


def test_kayseri_golden_rule_path_with_llm_check(monkeypatch):
    # Test rule-first path with FORCE_LLM_AT_LEAST_ONCE_PER_MESSAGE enabled
    monkeypatch.setattr(GroupBasedParser, 'get_group_config', lambda self, group_name: {'parser_type': 'rule_based'})
    gp = GroupBasedParser(force_llm_at_least_once_per_message=True)

    # Mock parse_with_rules to return an initially messy set where ilce contains garbage
    def fake_rules_parse(self, message, message_id):
        shipments = []
        lines = [l.strip() for l in message.split('\n') if l.strip()]
        for i, ln in enumerate(lines):
            # produce noisy ilce tokens
            shipments.append({'nereden_il': 'KAYSERİ', 'nereden_ilce': 'MERKEZ', 'nereye_il': 'İZMİR', 'nereye_ilce': '13-60AÇIK TIRSÜNGER26', 'aciklama': ln})
        return shipments

    monkeypatch.setattr(GroupBasedParser, 'parse_with_rules', fake_rules_parse)

    # Mock location check to clean ilce fields
    def fake_loc_check(self, shipments, message, config):
        for sh in shipments:
            sh['nereye_ilce'] = sh['nereye_ilce'].split()[0] if sh['nereye_ilce'] else 'MERKEZ'
        return shipments

    monkeypatch.setattr(GroupBasedParser, '_location_check_with_llm', fake_loc_check)

    results = gp.parse_message({'body': KAYSERI_MSG, 'id': 'kayseri_2', 'chat_name': 'KAYSERI TEST'})
    assert results
    for sh in results:
        assert '13-60' not in sh.get('nereye_ilce', '')
        assert 'YÜKÜSTÜ' not in sh.get('nereye_ilce', '')
