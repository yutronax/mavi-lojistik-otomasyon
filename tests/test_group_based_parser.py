import sys
import os
import pytest
# Ensure repository root is on sys.path so 'src' package can be imported
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.parsers.group_based_parser import (
    determine_message_shape,
    GroupBasedParser,
)


def test_determine_message_shape_route_pair():
    text = "KONYA -> ANKARA 1 TIR"
    assert determine_message_shape(text) == "route_pair"


def test_determine_message_shape_list():
    text = "1) KONYA\n2) ANKARA\n3) İZMİR"
    assert determine_message_shape(text) == "list"


def test_extract_message_defaults_marker():
    parser = GroupBasedParser(api_key=None)
    # '1 TEKER' is not currently mapped to a vehicle shorthand; marker present but no known token => no defaults
    text = "GENEL: 1 TEKER\nKONYA -> ANKARA: 1 TEKER\nİZMİR -> ANTALYA: 1 TEKER"
    defaults = parser._extract_message_defaults(text)
    assert defaults == {}


def test_extract_message_defaults_occurrence():
    parser = GroupBasedParser(api_key=None)
    text = "KONYA -> ANKARA 10 TEKER\nİZMİR -> ANTALYA 10 TEKER\nSAMSUN -> TRABZON"
    defaults = parser._extract_message_defaults(text)
    # '10 TEKER' is not considered a global default by design (should not create message-level defaults)
    assert defaults == {}


def test_detect_types_in_text_truck():
    parser = GroupBasedParser(api_key=None)
    text = "10 TEKER KAMYON"
    types = parser._detect_types_in_text(text)
    assert 'arac_tipi' in types or 'yuk_tipi' in types


def test_extract_message_defaults_with_genel_marker():
    parser = GroupBasedParser(api_key=None)
    text = "GENEL: KAPALI\nANKARA -> İZMİR\nKONYA -> ANTALYA"
    defaults = parser._extract_message_defaults(text)
    # Marker 'GENEL' + token 'KAPALI' should cause kasa_tipi to be applied as a message default
    assert defaults.get('kasa_tipi') == ['KAPALI']


def test_extract_message_defaults_with_toplu_marker_and_vehicle():
    parser = GroupBasedParser(api_key=None)
    text = "TOPLU: 1360\nANKARA -> İZMİR\nKONYA -> ANTALYA"
    defaults = parser._extract_message_defaults(text)
    # Marker 'TOPLU' with numeric vehicle shorthand should apply as message default
    assert defaults.get('arac_tipi') == ['1360']


def test_extract_message_defaults_with_hepsi_variant():
    parser = GroupBasedParser(api_key=None)
    text = "HEPSİ: FRİGO\nKONYA -> İZMİR"
    defaults = parser._extract_message_defaults(text)
    # Variant marker 'HEPSİ' should also be recognized
    assert defaults.get('kasa_tipi') == ['FRİGO']
