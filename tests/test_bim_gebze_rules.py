import re
from src.parsers.group_based_parser import GroupBasedParser
import json


def find_message_with_text(substr):
    with open('mesajlar.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    for m in data.get('messages', []):
        if substr in (m.get('body') or ''):
            return m
    return None


def test_bim_gebze_message_price_and_locations():
    gp = GroupBasedParser()
    msg = find_message_with_text('24 SAAT YÜKLEME')
    assert msg, 'No BİM/GEBZE test message found in mesajlar.json'
    results = gp.parse_message(msg)
    # At least 1 shipment expected
    assert results and len(results) >= 1
    for sh in results:
        # Destination and district not empty
        assert sh.get('nereye_il'), f"Missing nereye_il in {sh}"
        assert sh.get('nereye_ilce'), f"Missing nereye_ilce in {sh}"
        # Price must not be a decimal number like 13.60
        price = sh.get('fiyat', '') or ''
        assert not re.match(r"^\s*\d+[\.,]\d+\s*$", price), f"Unexpected numeric price in BİM message: {price}"
        # If organizer mis-extracted a price, it should be 'SORUNUZ'
        if re.search(r"\d+[\.,]\d+", price):
            pytest.fail(f"Numeric price remained: {price}")
        # If earlier parser extracted 13.60, it should have been moved to arac_tipi
        # (non-fatal; check only that fiyat != numeric)

