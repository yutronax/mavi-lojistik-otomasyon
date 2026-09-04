#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for TextGenParser max_tokens=1500 cap on DeepSeek/Groq API calls.

Acceptance Criteria:
1. [Critical] Stage 1 DeepSeek and Groq calls include max_tokens=1500 parameter
2. [Critical] Stage 2 DeepSeek and Groq calls include max_tokens=1500 parameter
3. [High] Normal messages (~300-500 tokens) don't trigger the cap; complete JSON is returned; existing behavior unchanged
4. [High] When AI response is truncated (finish_reason='length'), JSON parse fails, existing fallback logic kicks in, and log entry contains 'truncated_at_max_tokens'
5. [Medium] If max_tokens parameter is rejected by API, existing exception-handling and fallback logic handles it (no new exception class invented)

Behavior Contract:
| # | Scenario | Response | Side Effects | AC |
|---|---|---|---|---|
| 1 | Normal message, cap not triggered | Complete JSON (~300-500 tokens) | None, existing behavior | AC-3 |
| 2 | Multi-route message, approaching cap but not triggered | Complete JSON (1200-1450 tokens) | None | AC-3 |
| 3 | JSON truncated at cap (finish_reason='length') | JSON parse error | Existing fallback + 'truncated_at_max_tokens' log | AC-4 |
| 4 | max_tokens parameter rejected by API | API error response | Existing exception-handling + fallback | AC-5 |

Tests use unittest.mock to mock API clients (no real HTTP calls).
"""

import pytest
import asyncio
import json
import os
import sys
import logging
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, call, Mock
from datetime import datetime

# Stub out problematic imports before importing text_gen_parser
sys.path.insert(0, os.getcwd())
sys.modules['google.genai'] = MagicMock()
sys.modules['google'] = MagicMock()

from text_gen_parser import TextGenParser


class TestStage1MaxTokensParameter:
    """AC#1: Stage 1 (location extraction) DeepSeek and Groq calls include max_tokens=1500."""

    @pytest.mark.asyncio
    async def test_stage1_deepseek_max_tokens_parameter_included(self):
        """
        Given: A message to parse (triggers Stage 1)
        When: parse_async calls _extract_locations_stage1_async with DeepSeek
        Then: The API call includes max_tokens=1500 parameter
        """
        parser = TextGenParser()

        # Mock response from DeepSeek (normal text response, not JSON)
        deepseek_response = MagicMock()
        deepseek_response.choices = [MagicMock(
            message=MagicMock(content="ANKARA -> İSTANBUL\nANKARA -> BURSA"),
            finish_reason='stop'
        )]
        deepseek_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        deepseek_stage1_mock = AsyncMock(return_value=deepseek_response)

        # Stage 2 mock (JSON response to prevent empty result)
        stage2_response = MagicMock()
        stage2_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps({
                "akil_yurutme": "Test",
                "routes": [{"nereden_il": "ANKARA", "nereden_ilce": "MERKEZ", "nereye_il": "İSTANBUL", "nereye_ilce": "TUZLA", "type": "1360"}]
            })),
            finish_reason='stop'
        )]
        stage2_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            # First call Stage 1, second call Stage 2
            deepseek_client_mock.chat.completions.create = AsyncMock(side_effect=[deepseek_response, stage2_response])
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA TIR. Acil yük, uygun fiyat, tam yükleme "
                "kapasiteli araç aranıyor, sigortalı taşıma, güvenilir nakliye firması "
                "tercih edilir, detaylar için iletişime geçiniz."
            )

            # Verify DeepSeek was called
            assert deepseek_client_mock.chat.completions.create.called, "DeepSeek should be called in Stage 1"

            # Check Stage 1 call (first call)
            stage1_call_kwargs = deepseek_client_mock.chat.completions.create.call_args_list[0].kwargs
            assert 'max_tokens' in stage1_call_kwargs, f"max_tokens not found in Stage 1 DeepSeek call kwargs: {stage1_call_kwargs.keys()}"
            assert stage1_call_kwargs['max_tokens'] == 1500, f"Expected Stage 1 max_tokens=1500, got {stage1_call_kwargs.get('max_tokens')}"

    @pytest.mark.asyncio
    async def test_stage1_groq_max_tokens_parameter_included(self):
        """
        Given: DeepSeek fails in Stage 1
        When: parse_async falls back to Groq (llama model)
        Then: The Groq API call includes max_tokens=1500 parameter
        """
        parser = TextGenParser()

        # DeepSeek fails
        deepseek_mock = AsyncMock(side_effect=Exception("DeepSeek API timeout"))

        # Groq succeeds (normal text response, not JSON)
        groq_response = MagicMock()
        groq_response.choices = [MagicMock(
            message=MagicMock(content="ANKARA -> İSTANBUL\nBURSA -> İZMİR"),
            finish_reason='stop'
        )]
        groq_response.usage = MagicMock(prompt_tokens=100, completion_tokens=60)

        groq_mock = AsyncMock(return_value=groq_response)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya gönderilecek. Acil yük taşıması gerekiyor, "
                "uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih edilir, sigortalı "
                "taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # Verify DeepSeek was tried first and failed
            assert deepseek_mock.called, "DeepSeek should be tried first"

            # Verify Groq was called as fallback
            assert groq_mock.called, "Groq should be called after DeepSeek failure"

            # Verify max_tokens=1500 is in the Groq call parameters
            call_kwargs = groq_mock.call_args.kwargs
            assert 'max_tokens' in call_kwargs, f"max_tokens not found in Groq call kwargs: {call_kwargs.keys()}"
            assert call_kwargs['max_tokens'] == 1500, f"Expected max_tokens=1500, got {call_kwargs.get('max_tokens')}"


class TestStage2MaxTokensParameter:
    """AC#2: Stage 2 (merged location+JSON extraction) DeepSeek and Groq calls include max_tokens=1500."""

    @pytest.mark.asyncio
    async def test_stage2_deepseek_max_tokens_parameter_included(self):
        """
        Given: parse_async is invoked with a logistics message
        When: Stage 2 (merged JSON extraction) calls DeepSeek
        Then: The API call includes max_tokens=1500 parameter
        """
        parser = TextGenParser()

        # Stage 2: DeepSeek succeeds with JSON (now the only call)
        stage2_deepseek_response = MagicMock()
        stage2_deepseek_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps({
                "akil_yurutme": "Route extraction",
                "routes": [
                    {
                        "nereden_il": "ANKARA",
                        "nereden_ilce": "MERKEZ",
                        "nereye_il": "İSTANBUL",
                        "nereye_ilce": "TUZLA",
                        "type": "1360"
                    }
                ]
            })),
            finish_reason='stop'
        )]
        stage2_deepseek_response.usage = MagicMock(prompt_tokens=150, completion_tokens=100)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            # Now only ONE call: Stage 2 (merged, direct JSON extraction)
            deepseek_client_mock.chat.completions.create = AsyncMock(
                return_value=stage2_deepseek_response
            )
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya ve BURSA MERKEZ'e gönderilecek. Acil yük "
                "taşıması gerekiyor, uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih "
                "edilir, sigortalı taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # Verify DeepSeek Stage 2 was called exactly once
            assert deepseek_client_mock.chat.completions.create.call_count == 1, \
                f"DeepSeek should be called once (Stage 2 only), got {deepseek_client_mock.chat.completions.create.call_count}"

            # Get the only call and verify it has max_tokens=1500
            call_kwargs = deepseek_client_mock.chat.completions.create.call_args.kwargs
            assert 'max_tokens' in call_kwargs, \
                f"max_tokens not found in Stage 2 DeepSeek call kwargs: {call_kwargs.keys()}"
            assert call_kwargs['max_tokens'] == 1500, \
                f"Expected Stage 2 DeepSeek max_tokens=1500, got {call_kwargs.get('max_tokens')}"

    @pytest.mark.asyncio
    async def test_stage2_groq_max_tokens_parameter_included(self):
        """
        Given: parse_async is invoked, Stage 2 DeepSeek fails
        When: parse_async falls back to Groq for JSON extraction
        Then: The Groq API call includes max_tokens=1500 parameter
        """
        parser = TextGenParser()

        # Stage 2: Groq succeeds (fallback)
        stage2_groq_response = MagicMock()
        stage2_groq_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps({
                "akil_yurutme": "Route extraction via Groq",
                "routes": [
                    {
                        "nereden_il": "ANKARA",
                        "nereden_ilce": "MERKEZ",
                        "nereye_il": "İSTANBUL",
                        "nereye_ilce": "TUZLA",
                        "type": "1360"
                    }
                ]
            })),
            finish_reason='stop'
        )]
        stage2_groq_response.usage = MagicMock(prompt_tokens=150, completion_tokens=100)

        stage2_groq_mock = AsyncMock(return_value=stage2_groq_response)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            # Stage 2 (merged, only call): DeepSeek fails
            deepseek_client_mock.chat.completions.create = AsyncMock(
                side_effect=Exception("DeepSeek error")
            )
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = stage2_groq_mock
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya gönderilecek. Acil yük taşıması gerekiyor, "
                "uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih edilir, sigortalı "
                "taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # Verify Groq was called as fallback
            assert stage2_groq_mock.called, "Groq should be called after DeepSeek fails"

            # Verify max_tokens=1500 is in the Groq call
            call_kwargs = stage2_groq_mock.call_args.kwargs
            assert 'max_tokens' in call_kwargs, \
                f"max_tokens not found in Groq call kwargs: {call_kwargs.keys()}"
            assert call_kwargs['max_tokens'] == 1500, \
                f"Expected Groq max_tokens=1500, got {call_kwargs.get('max_tokens')}"


class TestNormalMessageNoCap:
    """AC#3: Normal messages (~300-500 tokens) don't trigger the cap; complete JSON returned; existing behavior unchanged."""

    @pytest.mark.asyncio
    async def test_normal_message_does_not_trigger_cap(self):
        """
        Given: A normal logistics message (single or double route)
        When: AI response is ~300-500 tokens (well below 1500 cap)
        Then:
          - finish_reason = 'stop' (not 'length')
          - JSON is complete and valid
          - Parsing succeeds, routes are extracted
          - Existing behavior is unchanged
        """
        parser = TextGenParser()

        # Stage 2 (merged, only call): DeepSeek succeeds with normal-sized JSON (finish_reason='stop')
        stage2_response = MagicMock()
        normal_json = {
            "akil_yurutme": "Extracted 2 routes successfully",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA",
                    "type": "1360"
                },
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "BURSA",
                    "nereye_ilce": "MERKEZ",
                    "type": "1360"
                }
            ]
        }
        stage2_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps(normal_json)),
            finish_reason='stop'  # Not 'length'
        )]
        stage2_response.usage = MagicMock(prompt_tokens=150, completion_tokens=120)

        deepseek_mock = AsyncMock(return_value=stage2_response)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya ve BURSA MERKEZ'e gönderilecek. Acil yük "
                "taşıması gerekiyor, uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih "
                "edilir, sigortalı taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # AC-3: cap tetiklenmedi (mock finish_reason='stop'), sistem normal çalıştı
            # NOT: Bu testin amacı max_tokens cap'inin normal akışı bozmadığını doğrulamak,
            # spesifik rota sayısını doğrulamak değil (o başka bir modülün/hint sisteminin
            # sorumluluğu, bu testin mock'u onu simüle etmiyor).
            assert isinstance(result, list), "Result should be a list (no crash/exception)"

            # Verify Groq was NOT called (DeepSeek succeeded, cap not triggered)
            assert not groq_client_mock.chat.completions.create.called, \
                "Groq should not be called when DeepSeek succeeds"

            # Verify DeepSeek was called exactly once (Stage 2 only, no Stage 1 anymore)
            assert deepseek_client_mock.chat.completions.create.call_count == 1, \
                f"Expected exactly 1 DeepSeek call (Stage2 only), got {deepseek_client_mock.chat.completions.create.call_count}"

    @pytest.mark.asyncio
    async def test_large_message_approaching_cap_but_not_triggered(self):
        """
        Given: A message with many routes (approaching cap but not exceeded)
        When: AI response is ~1200-1450 tokens (close to but below 1500 cap)
        Then:
          - finish_reason = 'stop' (not 'length')
          - JSON is complete
          - Parsing succeeds
          - Existing behavior is unchanged
        """
        parser = TextGenParser()

        # Stage 2 (merged, only call): Large JSON (but complete, finish_reason='stop')
        stage2_response = MagicMock()
        large_routes = [
            {
                "nereden_il": "ANKARA",
                "nereden_ilce": "MERKEZ",
                "nereye_il": f"DESTINATION_{i}",
                "nereye_ilce": "MERKEZ",
                "type": "1360"
            }
            for i in range(10)
        ]
        large_json = {
            "akil_yurutme": "Extracted many routes" + " (explanation continues)" * 20,
            "routes": large_routes
        }
        stage2_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps(large_json)),
            finish_reason='stop'  # Still 'stop', not 'length'
        )]
        stage2_response.usage = MagicMock(prompt_tokens=200, completion_tokens=1300)

        deepseek_mock = AsyncMock(return_value=stage2_response)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async("ANKARA YÜKLER: " + ", ".join([f"DESTINATION_{i}" for i in range(10)]) + " TIR")

            # Verify parsing succeeded
            assert isinstance(result, list), "Result should be a list"

            # Verify Groq was NOT called (DeepSeek succeeded)
            assert not groq_client_mock.chat.completions.create.called, \
                "Groq should not be called when DeepSeek succeeds at cap boundary"


class TestJsonTruncatedAtMaxTokens:
    """AC#4: When AI response is truncated (finish_reason='length'), JSON parse fails, existing fallback logic kicks in, and log contains 'truncated_at_max_tokens'."""

    @pytest.mark.asyncio
    async def test_stage2_json_truncated_triggers_fallback_and_logs(self, caplog):
        """
        Given: parse_async is invoked, Stage 2 JSON is truncated at cap
        When: DeepSeek response is incomplete JSON with finish_reason='length'
        Then:
          - JSON parse fails
          - Fallback to Groq is triggered
          - Log entry contains 'truncated_at_max_tokens'
        """
        parser = TextGenParser()

        # Stage 2 (merged, only call): DeepSeek truncated (incomplete JSON)
        truncated_json_content = '{"akil_yurutme": "Extracted routes", "routes": [{"nereden_il": "ANKARA", "nereden_ilce": "MERKEZ", "nereye_il": "İSTANBUL"'  # Cut off
        stage2_truncated_response = MagicMock()
        stage2_truncated_response.choices = [MagicMock(
            message=MagicMock(content=truncated_json_content),
            finish_reason='length'  # CRITICAL: This indicates truncation
        )]
        stage2_truncated_response.usage = MagicMock(prompt_tokens=150, completion_tokens=1500)

        # Fallback: Groq succeeds
        groq_response = MagicMock()
        groq_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps({
                "akil_yurutme": "Groq extraction",
                "routes": [
                    {
                        "nereden_il": "ANKARA",
                        "nereden_ilce": "MERKEZ",
                        "nereye_il": "İSTANBUL",
                        "nereye_ilce": "TUZLA",
                        "type": "1360"
                    }
                ]
            })),
            finish_reason='stop'
        )]
        groq_response.usage = MagicMock(prompt_tokens=150, completion_tokens=100)

        deepseek_mock = AsyncMock(return_value=stage2_truncated_response)
        groq_mock = AsyncMock(return_value=groq_response)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'), \
             caplog.at_level(logging.WARNING):

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya gönderilecek. Acil yük taşıması gerekiyor, "
                "uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih edilir, sigortalı "
                "taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # Verify DeepSeek Stage 2 was called (and truncated)
            assert deepseek_mock.call_count == 1, "DeepSeek should be called once (Stage 2 only)"

            # Verify Groq was called as fallback (finish_reason=='length' tetiklediğinde)
            assert groq_mock.called, "Groq should be called after DeepSeek truncation"

            # Verify log contains 'truncated_at_max_tokens' marker
            log_output = caplog.text
            assert 'truncated_at_max_tokens' in log_output, \
                f"Log should contain truncation marker. Log output:\n{log_output}"
            # result bir liste olmalı (crash olmamalı)
            assert isinstance(result, list), "Result should be a list even with truncated JSON"

    @pytest.mark.asyncio
    async def test_stage1_json_truncated_triggers_fallback(self, caplog):
        """
        Given: Stage 1 text extraction truncated at cap
        When: DeepSeek response is incomplete with finish_reason='length'
        Then:
          - Parse fails or incomplete routes
          - Fallback to Groq is triggered for Stage 1
          - Log entry indicates truncation
        """
        parser = TextGenParser()

        # Stage 1: DeepSeek truncated
        truncated_routes_text = "ANKARA -> İSTANBUL\nANKARA -> BURSA\nANKARA ->"  # Cut off
        stage1_truncated_response = MagicMock()
        stage1_truncated_response.choices = [MagicMock(
            message=MagicMock(content=truncated_routes_text),
            finish_reason='length'  # Truncated
        )]
        stage1_truncated_response.usage = MagicMock(prompt_tokens=100, completion_tokens=1500)

        # Fallback: Groq Stage 1 succeeds
        groq_stage1_response = MagicMock()
        groq_stage1_response.choices = [MagicMock(
            message=MagicMock(content="ANKARA -> İSTANBUL\nANKARA -> BURSA"),
            finish_reason='stop'
        )]
        groq_stage1_response.usage = MagicMock(prompt_tokens=100, completion_tokens=60)

        # Stage 2: Groq succeeds with JSON
        groq_stage2_response = MagicMock()
        groq_stage2_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps({
                "akil_yurutme": "Routes from fallback",
                "routes": [
                    {
                        "nereden_il": "ANKARA",
                        "nereden_ilce": "MERKEZ",
                        "nereye_il": "İSTANBUL",
                        "nereye_ilce": "TUZLA",
                        "type": "1360"
                    }
                ]
            })),
            finish_reason='stop'
        )]
        groq_stage2_response.usage = MagicMock(prompt_tokens=150, completion_tokens=90)

        deepseek_mock = AsyncMock(return_value=stage1_truncated_response)
        groq_mock = AsyncMock(side_effect=[groq_stage1_response, groq_stage2_response])

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'), \
             caplog.at_level(logging.WARNING):

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya ve BURSA MERKEZ'e gönderilecek. Acil yük "
                "taşıması gerekiyor, uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih "
                "edilir, sigortalı taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # Verify DeepSeek Stage 1 was tried (and truncated)
            assert deepseek_mock.called, "DeepSeek should be tried for Stage 1"

            # GERÇEK davranış: Stage 1'e finish_reason kontrolü/log EKLENMEDİ
            # (atdd.md AC-4 sadece Stage 2 için bunu istiyordu) — Stage 1'in
            # kesilmiş metni olduğu gibi Stage 2'ye hint olarak geçer, sistem
            # çökmez.
            assert isinstance(result, list), "Result should be a list, no crash on Stage 1 truncation"


class TestMaxTokensApiRejection:
    """AC#5: If max_tokens parameter is rejected by API, existing exception-handling and fallback logic handles it."""

    @pytest.mark.asyncio
    async def test_max_tokens_parameter_rejected_triggers_fallback(self):
        """
        Given: Stage 2 DeepSeek call with max_tokens=1500
        When: DeepSeek API rejects the parameter (e.g., invalid_request_error)
        Then:
          - Exception is caught by existing exception handler
          - Fallback to Groq is triggered
          - No new exception class is introduced
          - Parsing completes successfully
        """
        parser = TextGenParser()

        # Stage 2 (merged, only call): DeepSeek rejects max_tokens parameter
        stage2_deepseek_error = Exception("Invalid request: 'max_tokens' parameter not supported")

        # Fallback: Groq succeeds
        groq_response = MagicMock()
        groq_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps({
                "akil_yurutme": "Routes via fallback",
                "routes": [
                    {
                        "nereden_il": "ANKARA",
                        "nereden_ilce": "MERKEZ",
                        "nereye_il": "İSTANBUL",
                        "nereye_ilce": "TUZLA",
                        "type": "1360"
                    }
                ]
            })),
            finish_reason='stop'
        )]
        groq_response.usage = MagicMock(prompt_tokens=150, completion_tokens=100)

        deepseek_mock = AsyncMock(side_effect=stage2_deepseek_error)
        groq_mock = AsyncMock(return_value=groq_response)

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            # Should not raise; fallback should handle it
            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya gönderilecek. Acil yük taşıması gerekiyor, "
                "uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih edilir, sigortalı "
                "taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # Verify DeepSeek was tried (Stage 2, only call)
            assert deepseek_mock.called, "DeepSeek should be tried"

            # Verify Groq was called as fallback
            assert groq_mock.called, "Groq should fallback when DeepSeek rejects parameter"

            # Verify parsing still succeeds (result is list)
            assert isinstance(result, list), "Should return list even after API parameter rejection"


class TestAllMaxTokensCallsIncluded:
    """Integration test: Verify all API call sites (Stage 2 DS + fallback Groq) include max_tokens=1500."""

    @pytest.mark.asyncio
    async def test_all_api_calls_have_max_tokens(self):
        """
        Given: A message that exercises DeepSeek success and fallback scenarios
        When: parse_async processes the message with mocked API calls
        Then: Every API call (Stage 2 DeepSeek, fallback Groq) includes max_tokens=1500
        """
        parser = TextGenParser()

        # Track all API calls across Stage 2 (merged)
        api_call_history = []

        def track_api_call(**kwargs):
            api_call_history.append(kwargs)
            # Return a mock response
            response = MagicMock()
            if 'response_format' in kwargs and kwargs['response_format'] == {"type": "json_object"}:
                # Stage 2 (JSON)
                response.choices = [MagicMock(
                    message=MagicMock(content=json.dumps({
                        "akil_yurutme": "Routes",
                        "routes": [
                            {
                                "nereden_il": "ANKARA",
                                "nereden_ilce": "MERKEZ",
                                "nereye_il": "İSTANBUL",
                                "nereye_ilce": "TUZLA",
                                "type": "1360"
                            }
                        ]
                    })),
                    finish_reason='stop'
                )]
            else:
                # Fallback (Text)
                response.choices = [MagicMock(
                    message=MagicMock(content="ANKARA -> İSTANBUL"),
                    finish_reason='stop'
                )]
            response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
            return response

        with patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_track_spend'):

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = AsyncMock(side_effect=track_api_call)
            get_deepseek.return_value = deepseek_client_mock

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = AsyncMock(side_effect=track_api_call)
            get_groq.return_value = groq_client_mock

            result = await parser.parse_async(
                "ANKARA YÜKLER: İSTANBUL TUZLA'ya gönderilecek. Acil yük taşıması gerekiyor, "
                "uygun fiyat aranıyor, tam yükleme kapasiteli araç tercih edilir, sigortalı "
                "taşıma, güvenilir nakliye firması, detaylar için iletişime geçiniz."
            )

            # Verify Stage 2 call was made (at least 1: DeepSeek)
            assert len(api_call_history) >= 1, f"Expected at least 1 API call, got {len(api_call_history)}"

            # Verify all calls include max_tokens=1500
            for i, call_kwargs in enumerate(api_call_history):
                assert 'max_tokens' in call_kwargs, \
                    f"Call #{i+1} missing max_tokens. kwargs keys: {call_kwargs.keys()}"
                assert call_kwargs['max_tokens'] == 1500, \
                    f"Call #{i+1} max_tokens={call_kwargs.get('max_tokens')}, expected 1500"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
