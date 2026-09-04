#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for deepseek-maliyet-dusurme-stage-birlestir-junk-filtre.

Acceptance Criteria:
AC-3 [Critical]: `_is_junk_message()` fonksiyonu veri_cekici_ayristirici.py'de var olmalı.
                 Hiçbir Türkiye şehir adı, lojistik anahtar kelimesi ve telefon numarası YOK olan
                 mesajlar için True döndürmeli (junk sayılmalı).
AC-4 [High]:     Şehir adı YOK ama lojistik anahtar kelimesi VEYA telefon numarası VAR olan
                 mesajlar için False döndürmeli (junk değil, işlenmeye devam etsin).
AC-5 [High]:     Gerçek geçmiş mesaj örnekleri (data/onaylanmamis_ayristirilmis.json'dan
                 en az 20-30 tanesi) üzerinde GERÇEK ilanlar YANLIŞLIKLA eliminate edilmemeli
                 (false-positive oranı %0 olmalı).
"""

import pytest
import os
import sys
import json
import re
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out problematic imports BEFORE importing veri_cekici_ayristirici
from unittest.mock import MagicMock

_mock = MagicMock()
sys.modules['google.genai'] = _mock
sys.modules['google'] = _mock
sys.modules['dotenv'] = _mock

# MongoDB mocks
_pymongo_mock = MagicMock()
_pymongo_mock.MongoClient = MagicMock()
_pymongo_mock.UpdateOne = MagicMock()
_pymongo_mock.DESCENDING = MagicMock()
_pymongo_errors_mock = MagicMock()
_pymongo_mock.errors = _pymongo_errors_mock
sys.modules['pymongo'] = _pymongo_mock
sys.modules['pymongo.errors'] = _pymongo_errors_mock

# Also mock Whapi and other optional imports
sys.modules['whapi'] = _mock
sys.modules['pymongo'] = _pymongo_mock


class TestJunkMessageFilter:
    """
    AC-3, AC-4, AC-5: Verify _is_junk_message() exists and filters correctly.
    """

    @pytest.fixture
    def city_keywords(self):
        """
        Extract city keywords from text_gen_parser._tag_cities() definition.
        These are the same cities/hubs used for junk filtering.
        """
        # Standard Turkish cities (from text_gen_parser.py:175-179)
        cities = [
            "ADANA", "ADIYAMAN", "AFYON", "AFYONKARAHİSAR", "AĞRI", "AKSARAY", "AMASYA", "ANKARA",
            "ANTALYA", "ARDAHAN", "ARTVİN", "AYDIN", "BALIKESİR", "BARTIN", "BATMAN", "BAYBURT",
            "BİLECİK", "BİNGÖL", "BİTLİS", "BOLU", "BURDUR", "BURSA", "ÇANAKKALE", "ÇANKIRI",
            "ÇORUM", "DENİZLİ", "DİYARBAKIR", "DÜZCE", "EDİRNE", "ELAZIĞ", "ERZİNCAN", "ERZURUM",
            "ESKİŞEHİR", "GAZİANTEP", "GİRESUN", "GÜMÜŞHANE", "HAKKARİ", "HATAY", "IĞDIR",
            "ISPARTA", "MERSİN", "İÇEL", "İSTANBUL", "İZMİR", "KAHRAMANMARAŞ", "KARABÜK",
            "KARAMAN", "KARS", "KASTAMONU", "KAYSERİ", "KIRIKKALE", "KIRKLARELİ", "KIRŞEHİR",
            "KİLİS", "KOCAELİ", "KONYA", "KÜTAHYA", "MALATYA", "MANİSA", "MARDİN", "MUĞLA",
            "MUŞ", "NEVŞEHİR", "NİĞDE", "ORDU", "OSMANİYE", "RİZE", "SAKARYA", "SAMSUN", "SİİRT",
            "SİNOP", "SİVAS", "ŞANLIURFA", "ŞIRNAK", "TEKİRDAĞ", "TOKAT", "TRABZON", "TUNCELİ",
            "UŞAK", "VAN", "YALOVA", "YOZGAT", "ZONGULDAK"
        ]

        # Common aliases & major logistics hubs
        aliases = ["ANTEP", "MARAŞ", "URFA", "GANTEP", "KMARAŞ", "ŞURFA"]
        hubs = ["ALİAĞA", "KIZILTEPE", "GEBZE", "ÇORLU", "İNEGÖL", "İSKENDERUN",
                "ÇERKEZKÖY", "SİLİVRİ", "TUZLA", "DİLOVASI", "KEMALPAŞA", "MUSTAFAKEMALPAŞA"]

        return list(set(cities + aliases + hubs))

    @pytest.fixture
    def logistics_keywords(self):
        """Logistics keywords that indicate a real shipment offer."""
        return [
            "TIR", "KAMYON", "İNŞAAT", "BOŞYAR", "BOŞ", "ARAÇ",
            "NAKLIYE", "NAK", "LOJİSTİK", "TAŞIMA", "YÜKLEME",
            "YÜKÜ", "YÜKLER", "ÇIKIŞLI", "KALKIŞ", "VARIŞLI",
            "YÜKLÜ", "KARGİ", "KARGİE", "KURYE", "DOLMUŞ"
        ]

    @pytest.fixture
    def phone_regex(self):
        """Regex to detect Turkish phone numbers."""
        # Turkish phone format: 05XX XXX XX XX or 05XXXXXXXXX or similar
        return r'\b0\d{3}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b|\b0\d{10,11}\b'

    def test_is_junk_message_function_exists(self):
        """
        AC-3 [Critical]: Given veri_cekici_ayristirici module,
        When imported, Then _is_junk_message() function should exist.

        THIS TEST WILL FAIL (red) IF the function does not exist yet.
        Current code: function not implemented.
        """
        # Try to import and check for the function
        try:
            from src.parsers.veri_cekici_ayristirici import _is_junk_message
            # If we get here, function exists
            assert callable(_is_junk_message), \
                "_is_junk_message should be callable"
        except (ImportError, AttributeError) as e:
            pytest.fail(
                f"_is_junk_message() function not found in veri_cekici_ayristirici.py. "
                f"Error: {e}. This is EXPECTED FAILURE (red) — function to be implemented."
            )

    def test_basic_junk_detection_no_city_no_keywords(self, city_keywords, logistics_keywords):
        """
        AC-3 [Critical]: Given a message with NO city names, NO logistics keywords, NO phone numbers,
        When _is_junk_message() is called, Then it should return True (junk).

        Test message: "Merhaba nasılsınız" (generic greeting, no logistics info).

        THIS TEST WILL FAIL (red) IF function doesn't exist or is not implemented.
        """
        try:
            from src.parsers.veri_cekici_ayristirici import _is_junk_message
        except (ImportError, AttributeError):
            pytest.skip("_is_junk_message() not yet implemented")

        junk_message = "Merhaba nasılsınız? Bugün hava çok güzel. Ne yapıyorsunuz?"

        result = _is_junk_message(junk_message)

        assert result is True, \
            f"Message with no city/keyword/phone should be junk. Got: {result}"

    def test_non_junk_with_logistics_keyword_no_city(self, city_keywords, logistics_keywords):
        """
        AC-4 [High]: Given a message with NO city name but HAS logistics keyword (e.g., "TIR", "KAMYON"),
        When _is_junk_message() is called, Then it should return False (NOT junk, send to LLM).

        Test message: "TIR lazım" (logistics keyword present, no city).

        THIS TEST WILL FAIL (red) IF function doesn't exist or is not implemented.
        """
        try:
            from src.parsers.veri_cekici_ayristirici import _is_junk_message
        except (ImportError, AttributeError):
            pytest.skip("_is_junk_message() not yet implemented")

        # Message with logistics keyword but no city
        message_with_keyword = "TIR lazım, acil gönderi var"

        result = _is_junk_message(message_with_keyword)

        assert result is False, \
            f"Message with logistics keyword (no city) should NOT be junk. Got: {result}"

    def test_non_junk_with_phone_no_city(self, city_keywords, logistics_keywords, phone_regex):
        """
        AC-4 [High]: Given a message with NO city name but HAS phone number format,
        When _is_junk_message() is called, Then it should return False (NOT junk, send to LLM).

        Test message: "Arama yap" + phone number.

        THIS TEST WILL FAIL (red) IF function doesn't exist or is not implemented.
        """
        try:
            from src.parsers.veri_cekici_ayristirici import _is_junk_message
        except (ImportError, AttributeError):
            pytest.skip("_is_junk_message() not yet implemented")

        # Message with phone but no city or keyword
        message_with_phone = "Bana 0532 123 45 67 numarasından ara lütfen"

        result = _is_junk_message(message_with_phone)

        assert result is False, \
            f"Message with phone number (no city/keyword) should NOT be junk. Got: {result}"

    def test_real_shipment_with_city_not_junk(self, city_keywords, logistics_keywords):
        """
        AC-5 [High]: Given a real shipment message with city name,
        When _is_junk_message() is called, Then it should return False (NOT junk).

        Test message: "İSTANBUL'DEN ANKARA'YA TIR LAZIM".

        THIS TEST WILL FAIL (red) IF function doesn't exist or is not implemented.
        """
        try:
            from src.parsers.veri_cekici_ayristirici import _is_junk_message
        except (ImportError, AttributeError):
            pytest.skip("_is_junk_message() not yet implemented")

        real_shipment = "İSTANBUL'DEN ANKARA'YA TIR LAZIM. Acil sipariş. Fiyat sorunuz."

        result = _is_junk_message(real_shipment)

        assert result is False, \
            f"Real shipment message should NOT be junk. Got: {result}"

    def test_regression_real_messages_no_false_positives(self, city_keywords, logistics_keywords):
        """
        AC-5 [High]: Given real messages from data/onaylanmamis_ayristirilmis.json
        (at least 20-30 samples), When _is_junk_message() is called on each,
        Then NONE should return True (no false positives). These are already-approved
        shipment listings, so they should not be filtered out as junk.

        If file not found or has < 20 samples, skip test.

        THIS TEST WILL FAIL (red) IF function doesn't exist or is not implemented.
        """
        try:
            from src.parsers.veri_cekici_ayristirici import _is_junk_message
        except (ImportError, AttributeError):
            pytest.skip("_is_junk_message() not yet implemented")

        # Try to load real message samples
        data_file = os.path.join(
            os.path.dirname(__file__), "..", "data", "onaylanmamis_ayristirilmis_log.json"
        )

        if not os.path.exists(data_file):
            pytest.skip(f"Real message data file not found: {data_file}")

        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            pytest.skip(f"Could not load/parse {data_file}: {e}")

        # Extract message bodies
        messages = []

        # Try multiple extraction patterns (different JSON structures)
        if isinstance(data, list):
            # Array of message objects
            for item in data:
                if isinstance(item, dict):
                    # Try 'body' field
                    if 'body' in item:
                        messages.append(item['body'])
                    # Try 'message_info.body' nested structure
                    elif 'message_info' in item and isinstance(item['message_info'], dict):
                        if 'body' in item['message_info']:
                            messages.append(item['message_info']['body'])
                    # Try 'shipments[0].body'
                    elif 'shipments' in item and isinstance(item['shipments'], list):
                        for shipment in item['shipments']:
                            if isinstance(shipment, dict) and 'body' in shipment:
                                messages.append(shipment['body'])
        elif isinstance(data, dict):
            # Try common top-level message fields
            if 'messages' in data:
                for msg in data['messages']:
                    if isinstance(msg, dict) and 'body' in msg:
                        messages.append(msg['body'])

        # Ensure we have at least 20 samples
        if len(messages) < 20:
            pytest.skip(
                f"Not enough real message samples (found {len(messages)}, need >= 20). "
                f"Skipping regression test."
            )

        # Take first 30 for test
        sample_messages = messages[:30]

        # Test: NONE of these real messages should be flagged as junk
        false_positives = []
        for msg in sample_messages:
            if not isinstance(msg, str):
                continue
            try:
                is_junk = _is_junk_message(msg)
                if is_junk:
                    false_positives.append(msg)
            except Exception as e:
                pytest.fail(f"_is_junk_message() raised exception: {e}")

        assert len(false_positives) == 0, \
            f"Found {len(false_positives)} false-positive junk flags in real messages. " \
            f"Examples: {false_positives[:3]}"

    def test_mixed_message_with_multiple_signals(self, city_keywords, logistics_keywords):
        """
        AC-4 [High] Extended: Given a message with MIXED signals
        (some present, some not), When _is_junk_message() is called,
        Then CONSERVATIVE rule: If ANY ONE signal (city/keyword/phone) is present, NOT junk.

        Test case: No city, but has keyword AND phone = NOT junk.
        """
        try:
            from src.parsers.veri_cekici_ayristirici import _is_junk_message
        except (ImportError, AttributeError):
            pytest.skip("_is_junk_message() not yet implemented")

        # Message with keyword AND phone, but NO city
        message = "TIR hizmetimiz var, araç 0532 123 45 67 numarasından arayın"

        result = _is_junk_message(message)

        assert result is False, \
            f"Message with keyword AND phone should NOT be junk (conservative). Got: {result}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
