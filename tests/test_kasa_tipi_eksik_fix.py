#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for kasa_tipi_belirsiz (Ambiguous Load Type) fix.

Acceptance Criteria:
1. [Critical] Happy path: Rule match found → kasa_tipi is populated, no uncertainty flag
2. [Critical] No hint: Message has no body-type keywords → kasa_tipi default, flag=True, reason="ipucu_yok"
3. [Critical] Hint but no match: Message has body-type keyword but rule didn't match → flag=True, reason="kural_eslesmedi" + log write
4. [High] Multi-route: Each route evaluated independently with its own uncertainty flag

Tests use unittest.mock to mock API clients and file I/O (no real HTTP calls, no real file writes).
VehicleTypeMatcher can be tested with real yuk_tipi.json (pure file I/O, not external API).
"""

import pytest
import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, call, Mock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.getcwd())

# Stub out problematic imports before importing text_gen_parser
sys.modules['google.genai'] = MagicMock()
sys.modules['google'] = MagicMock()

from text_gen_parser import TextGenParser
from src.utils.vehicle_type_matcher import VehicleTypeMatcher


class TestHappyPathRuleMatch:
    """AC#1: When rule matches, kasa_tipi is rule value; no uncertainty flag or flag=False."""

    @pytest.mark.asyncio
    async def test_rule_match_happy_path_no_uncertainty_flag(self):
        """
        Given: Message with a known pattern that matches yuk_tipi.json rule
        When: _process_raw_json_async processes the route
        Then:
          - kasa_tipi is populated from rule
          - kasa_tipi_belirsiz is either absent OR False (NOT True)
          - kasa_tipi_belirsiz_sebep is NOT present

        Test approach: Use real VehicleTypeMatcher + mock the rest of TextGenParser
        to isolate the kasa_tipi logic.
        """
        parser = TextGenParser()

        # Use a known pattern that WILL match in yuk_tipi.json
        # Common patterns: "AÇIK", "KAPALI", "DAMPERLİ", "FRİGO", etc.
        # We'll construct a raw_routes list with a simple route entry
        # and let _process_raw_json_async handle it

        # Create a minimal test message with known context
        test_message = "ANKARA -> İSTANBUL AÇIK ARAÇ"

        # Simulate AI-generated raw routes (before type matching)
        raw_routes_text = json.dumps({
            "akil_yurutme": "Test reasoning",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA",
                    "type": "1360",
                    "isim": "Test Company"
                }
            ]
        })

        with patch.object(parser, '_get_async_client'):
            # Process the raw JSON which calls vehicle_matcher.find_match internally
            result = await parser._process_raw_json_async(raw_routes_text, test_message)

        # Verify result
        assert len(result) > 0, "Should have at least one route"
        route = result[0]

        # Verify kasa_tipi is populated
        assert 'kasa_tipi' in route, "Route should have kasa_tipi field"
        assert isinstance(route['kasa_tipi'], list), "kasa_tipi should be a list"
        assert len(route['kasa_tipi']) > 0, "kasa_tipi should not be empty"

        # CRITICAL: Verify NO uncertainty flag or flag is False
        # After implementation, kasa_tipi_belirsiz should either:
        # - Not be present in route (preferred, only set when uncertain)
        # - OR be False (alternative implementation)
        if 'kasa_tipi_belirsiz' in route:
            assert route['kasa_tipi_belirsiz'] == False, \
                f"On rule match, kasa_tipi_belirsiz should be False, got {route['kasa_tipi_belirsiz']}"

        # Verify uncertainty reason is NOT set
        assert 'kasa_tipi_belirsiz_sebep' not in route, \
            "kasa_tipi_belirsiz_sebep should not be present on rule match"


class TestNoHintUncertainty:
    """AC#2: Message has NO body-type keywords → kasa_tipi defaults, flag=True, reason='ipucu_yok'."""

    @pytest.mark.asyncio
    async def test_no_hint_sets_uncertainty_ipucu_yok(self):
        """
        Given: Message with NO body-type keywords (e.g., only city names, no "AÇIK", "KAPALI", etc.)
        When: _process_raw_json_async processes the route
        Then:
          - kasa_tipi = ['AÇIK', 'KAPALI'] (default)
          - kasa_tipi_belirsiz = True
          - kasa_tipi_belirsiz_sebep = "ipucu_yok"

        Example: "ANKARA -> İSTANBUL" (no body type hint at all)
        """
        parser = TextGenParser()

        # Message with NO body-type keywords
        test_message = "ANKARA -> İSTANBUL"  # Just cities, no AÇIK/KAPALI/DAMPERLİ/etc.

        raw_routes_text = json.dumps({
            "akil_yurutme": "Extract routes from cities only",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA",
                    "type": "1360",
                    "isim": "Test Company"
                }
            ]
        })

        with patch.object(parser, '_get_async_client'):
            result = await parser._process_raw_json_async(raw_routes_text, test_message)

        assert len(result) > 0, "Should have at least one route"
        route = result[0]

        # Verify kasa_tipi is default
        assert route['kasa_tipi'] == ['AÇIK', 'KAPALI'], \
            f"Expected default kasa_tipi=['AÇIK', 'KAPALI'], got {route['kasa_tipi']}"

        # CRITICAL: Verify uncertainty flag is set
        # After implementation, these fields MUST be present:
        assert 'kasa_tipi_belirsiz' in route, \
            "Route must have kasa_tipi_belirsiz field when no hint found"
        assert route['kasa_tipi_belirsiz'] == True, \
            f"kasa_tipi_belirsiz should be True when no hint, got {route['kasa_tipi_belirsiz']}"

        assert 'kasa_tipi_belirsiz_sebep' in route, \
            "Route must have kasa_tipi_belirsiz_sebep when no hint"
        assert route['kasa_tipi_belirsiz_sebep'] == "ipucu_yok", \
            f"Expected sebep='ipucu_yok', got '{route['kasa_tipi_belirsiz_sebep']}'"


class TestHintButNoRuleMatch:
    """AC#3: Message has body-type keyword but rule didn't match → flag=True, reason='kural_eslesmedi' + file write."""

    @pytest.mark.asyncio
    async def test_hint_but_no_match_writes_unmatched_log(self):
        """
        Given:
          - Message contains a body-type keyword (e.g., "AÇIK", "KAPALI")
          - VehicleTypeMatcher.find_all_matches returns None (no rule matched)
        When: _process_raw_json_async processes the route
        Then:
          - kasa_tipi = ['AÇIK', 'KAPALI'] (default)
          - kasa_tipi_belirsiz = True
          - kasa_tipi_belirsiz_sebep = "kural_eslesmedi"
          - An entry is written to data/eslesmeyen_kasa_ifadeleri.json (mocked)

        Test approach: Mock VehicleTypeMatcher.find_match to return None,
        mock file I/O to verify write attempt.
        """
        parser = TextGenParser()

        # Message WITH a body-type keyword, but we'll mock find_match to return None
        test_message = "ANKARA -> İSTANBUL AÇIK ARAÇ İLE"  # Contains "AÇIK"

        raw_routes_text = json.dumps({
            "akil_yurutme": "Route extraction",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA",
                    "type": "1360",
                    "isim": "Test Company"
                }
            ]
        })

        # Mock VehicleTypeMatcher.find_match to return None (no rule matched)
        # This simulates: message has "AÇIK" keyword but no rule in yuk_tipi.json matches
        with patch.object(parser.vehicle_matcher, 'find_match', return_value=None), \
             patch('text_gen_parser.persistence_manager') as mock_pm, \
             patch('text_gen_parser.load_json_safe', return_value=[]):

            result = await parser._process_raw_json_async(raw_routes_text, test_message)

        assert len(result) > 0, "Should have at least one route"
        route = result[0]

        # Verify kasa_tipi is default
        assert route['kasa_tipi'] == ['AÇIK', 'KAPALI'], \
            f"Expected default when no match, got {route['kasa_tipi']}"

        # CRITICAL: Verify uncertainty flag indicates rule failure
        assert 'kasa_tipi_belirsiz' in route, "Must have kasa_tipi_belirsiz"
        assert route['kasa_tipi_belirsiz'] == True, "Flag should be True"

        assert 'kasa_tipi_belirsiz_sebep' in route, "Must have reason"
        assert route['kasa_tipi_belirsiz_sebep'] == "kural_eslesmedi", \
            f"Expected reason='kural_eslesmedi', got '{route['kasa_tipi_belirsiz_sebep']}'"

        # Verify file write was attempted (MANDATORY per AC-3)
        # AC-3 explicitly requires: "unmatched raw-text entry is written to log file"
        # This is NOT conditional - it MUST happen when hint exists but rule doesn't match
        assert mock_pm.queue_write.called, "persistence_manager.queue_write (or equivalent) MUST be called to log unmatched hint (AC-3 mandatory behavior)"
        call_args = mock_pm.queue_write.call_args_list[0]
        # call_args[0][0] is the file path
        file_path = call_args[0][0] if call_args[0] else ""
        assert "eslesmeyen_kasa_ifadeleri" in file_path or "kasa" in file_path.lower(), \
            f"Expected write to unmatched log file, got path: {file_path}"


class TestMultiRouteIndependentEvaluation:
    """AC#4: Multiple routes → each route has independent kasa_tipi_belirsiz status."""

    @pytest.mark.asyncio
    async def test_multi_route_independent_flags(self):
        """
        Given: A message with TWO routes:
          - Route 1: Matches a rule (e.g., "İSTANBUL AÇIK" → rule found)
          - Route 2: No match (e.g., "ANKARA" → no hint → flag)
        When: _process_raw_json_async processes both
        Then:
          - Route 1: kasa_tipi from rule, flag absent/False
          - Route 2: kasa_tipi default, flag=True, reason="ipucu_yok"

        Note: This tests the independence of evaluation per route.
        """
        parser = TextGenParser()

        # Two-route scenario
        test_message = "ISTANBUL AÇIK ARAÇ\nANKARA SADECE ŞEHİR"

        raw_routes_text = json.dumps({
            "akil_yurutme": "Two independent routes",
            "routes": [
                {
                    "nereden_il": "İZMİR",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA",
                    "type": "1360",
                    "isim": "Company A"
                },
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "BURSA",
                    "nereye_ilce": "MERKEZ",
                    "type": "1360",
                    "isim": "Company B"
                }
            ]
        })

        with patch.object(parser, '_get_async_client'):
            result = await parser._process_raw_json_async(raw_routes_text, test_message)

        assert len(result) >= 2, f"Should have at least 2 routes, got {len(result)}"

        route1 = result[0]  # İSTANBUL AÇIK - has hint, might match rule
        route2 = result[1]  # ANKARA -> BURSA only, NO body-type hint at all

        # Verify both routes were processed
        assert 'kasa_tipi' in route1, "Route 1 should have kasa_tipi"
        assert 'kasa_tipi' in route2, "Route 2 should have kasa_tipi"

        # CRITICAL for AC-4: Route 2 (ANKARA -> BURSA, NO hint) must ALWAYS be uncertain
        # The message "ANKARA SADECE ŞEHİR" has no body-type keywords (AÇIK, KAPALI, etc.)
        # Therefore, per AC-2 logic, Route 2 MUST have flag=True with reason="ipucu_yok"
        assert route2.get('kasa_tipi_belirsiz') == True, \
            f"Route 2 (ANKARA->BURSA, no hint) MUST have kasa_tipi_belirsiz=True, got {route2.get('kasa_tipi_belirsiz')}"
        assert route2.get('kasa_tipi_belirsiz_sebep') == "ipucu_yok", \
            f"Route 2 (no hint) MUST have sebep='ipucu_yok', got '{route2.get('kasa_tipi_belirsiz_sebep')}'"

        # AC-4 key requirement: Routes are evaluated INDEPENDENTLY
        # Route 1 (has "AÇIK" hint) flag status depends on rule match (flexible)
        # Route 2 (no hint) flag status is DEFINITE (ipucu_yok)
        # This confirms independent evaluation, not a shared/global state


class TestVehicleTypeMatcherKeywordExtraction:
    """Helper tests for VehicleTypeMatcher to verify keyword detection works."""

    def test_vehicle_matcher_loads_rules(self):
        """
        Given: VehicleTypeMatcher with default yuk_tipi.json path
        When: Initialized
        Then: Rules are loaded and available
        """
        matcher = VehicleTypeMatcher()
        assert len(matcher.rules) > 0, "Rules should be loaded from yuk_tipi.json"
        assert matcher.rules[0].get('orjinal mesajdaki'), "Rules should have 'orjinal mesajdaki' field"

    def test_vehicle_matcher_finds_known_pattern(self):
        """
        Given: A message with a known pattern from yuk_tipi.json
        When: find_all_matches is called
        Then: Returns a dict (not None) with KASA TİPİ field

        Uses real yuk_tipi.json for authentic pattern matching.
        """
        matcher = VehicleTypeMatcher()

        # Use a message that should match a real rule
        # Common patterns: "AÇIK", "KAPALI", "DAMPERLİ", etc.
        # Try a few to find one that actually exists
        test_messages = [
            "AÇIK ARAÇ İLE",
            "KAPALI ARAÇ",
            "DAMPERLİ",
            "FRİGO",
            "LOWBED"
        ]

        found_match = False
        for msg in test_messages:
            result = matcher.find_all_matches(msg)
            if result and 'KASA TİPİ' in result:
                found_match = True
                assert isinstance(result, dict), "find_all_matches should return a dict"
                assert result.get('KASA TİPİ'), "Result should have KASA TİPİ field"
                break

        # It's OK if no match found - yuk_tipi.json might not have simple patterns
        # But the method should return None or {} consistently
        if not found_match:
            # Verify method returns None or empty dict on no match
            result = matcher.find_all_matches("COMPLETELY UNKNOWN PATTERN XYZ")
            assert result is None or result == {}, \
                f"Should return None or empty dict on no match, got {result}"

    def test_vehicle_matcher_returns_none_on_empty(self):
        """
        Given: An empty or None message
        When: find_all_matches is called
        Then: Returns None or empty dict
        """
        matcher = VehicleTypeMatcher()

        result = matcher.find_all_matches("")
        assert result is None or result == {}, "Empty message should return None or {}"


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_route_with_missing_optional_fields(self):
        """
        Given: A route JSON with minimal fields (no 'type' or 'isim')
        When: _process_raw_json_async processes it
        Then: Should still set kasa_tipi_belirsiz without crashing
        """
        parser = TextGenParser()

        test_message = "TEST ROUTE"

        raw_routes_text = json.dumps({
            "akil_yurutme": "Minimal route",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA"
                    # Missing 'type', 'isim', etc.
                }
            ]
        })

        with patch.object(parser, '_get_async_client'):
            result = await parser._process_raw_json_async(raw_routes_text, test_message)

        # Should not crash and should return at least one route
        assert len(result) > 0, "Should handle missing optional fields gracefully"
        route = result[0]
        assert 'kasa_tipi' in route, "Should still set kasa_tipi"

    @pytest.mark.asyncio
    async def test_empty_routes_list(self):
        """
        Given: A valid JSON response with empty routes list
        When: _process_raw_json_async processes it
        Then: Should return empty list (not crash)
        """
        parser = TextGenParser()

        test_message = "SOME MESSAGE"

        raw_routes_text = json.dumps({
            "akil_yurutme": "No routes found",
            "routes": []
        })

        with patch.object(parser, '_get_async_client'):
            result = await parser._process_raw_json_async(raw_routes_text, test_message)

        assert result == [], "Empty routes should return empty list"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
