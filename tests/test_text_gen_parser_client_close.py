#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for text_gen_parser.py client close() behavior (baileys-mesaj-guvenilirligi).

Acceptance Criteria (atdd.md):
1. [Critical] AC-2: Given text_gen_parser.py parse_async() her model denemesinde
   TAZE bir async client (AsyncOpenAI/AsyncGroq) oluşturuyor ve API çağrısından
   sonra HİÇBİR ZAMAN kapatmıyor, When bu client'lar GC tarafından sonradan
   finalize edilmeye çalışılır (çoğunlukla farklı/kapanmış bir asyncio.run()
   event loop'unda), Then bu artık "Event loop is closed" hatasına yol
   AÇMAMALI — her client kullanımından hemen sonra (başarı veya hata
   fark etmeksizin) await client.close() çağrılmalı (try/finally veya async with).

2. [Critical] AC-3: Given eşzamanlı 5+ worker thread'i (her biri kendi asyncio.run()
   çağrısıyla) gerçek (veya mock) AI çağrısı yapıyor, When bu senaryo testte
   simüle edilir, Then "RuntimeError: Event loop is closed" hatası oluşmamalı
   (kapatma garantisi test edilir).

Test Technique:
- pytest fixture: caplog, monkeypatch
- unittest.mock: patch, AsyncMock, call
- pytest-asyncio: @pytest.mark.asyncio for async tests
- Mock AsyncOpenAI/AsyncGroq to verify .close() is called
- Test both success and exception scenarios
- Multi-threaded test: ThreadPoolExecutor with asyncio.run() per thread

Key Assumptions (from plan.md):
- text_gen_parser.py:88-93 (_get_deepseek_client) ve line 83-86 (_get_async_client)
  döndürdükleri client'ların parse_async() içinde try/finally ile kapatılacağı
- google_genai.Client kapatılmayacak (senkron çağrı, asyncio.to_thread ile yapılıyor)
- Test henüz implementasyon olmadığı için başarısız olacak (red test)
"""

import pytest
import sys
import os
import asyncio
import logging
import json
from unittest.mock import patch, AsyncMock, MagicMock, call
from concurrent.futures import ThreadPoolExecutor
import tempfile

# Add project root to path
sys.path.insert(0, os.getcwd())

# Stub out problematic imports BEFORE importing TextGenParser
_mock = MagicMock()
sys.modules['google.genai'] = _mock
sys.modules['google'] = _mock
sys.modules['dotenv'] = _mock

# MongoDB mocks (more complex)
_pymongo_mock = MagicMock()
_pymongo_mock.MongoClient = MagicMock()
_pymongo_mock.UpdateOne = MagicMock()
_pymongo_mock.DESCENDING = MagicMock()
_pymongo_errors_mock = MagicMock()
_pymongo_mock.errors = _pymongo_errors_mock
sys.modules['pymongo'] = _pymongo_mock
sys.modules['pymongo.errors'] = _pymongo_errors_mock

from text_gen_parser import TextGenParser


@pytest.mark.asyncio
class TestClientClose:
    """AC-2, AC-3: Client close() guarantee"""

    async def test_deepseek_client_closed_on_success(self):
        """
        Given: parse_async() başarılı bir DeepSeek API çağrısı yapıyor
        When: AsyncOpenAI client oluşturuluyor ve API çağrısı başarılı oluyor
        Then: client.close() await edilmiş olmalı (başarı sonrası)
        """
        parser = TextGenParser()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"locations": []}'))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()

        with patch.object(parser, '_get_deepseek_client', return_value=mock_client):
            with patch.object(parser, '_get_async_client', return_value=AsyncMock()):
                with patch.object(parser, 'city_validator') as mock_validator:
                    mock_validator.validate_all = MagicMock(return_value={'valid': [], 'invalid': []})

                    try:
                        result = await parser.parse_async("İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON ACİL YÜK VAR TELEFON 0532 555 12 34 İLETİŞİME GEÇİNİZ LÜTFEN")
                    except Exception as e:
                        # Ignore parsing errors, focus on close() call
                        pass

                    # CRITICAL: close() must be called
                    mock_client.close.assert_called()

    async def test_deepseek_client_closed_on_exception(self):
        """
        Given: parse_async() DeepSeek API çağrısı exception fırlatıyor
        When: AsyncOpenAI client.create() ValueError/APIError fırlatıyor
        Then: client.close() yine de await edilmiş olmalı (try/finally garantisi)
        """
        parser = TextGenParser()

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        mock_client.close = AsyncMock()

        with patch.object(parser, '_get_deepseek_client', return_value=mock_client):
            with patch.object(parser, '_get_async_client', return_value=AsyncMock()):
                try:
                    result = await parser.parse_async("İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON ACİL YÜK VAR TELEFON 0532 555 12 34 İLETİŞİME GEÇİNİZ LÜTFEN")
                except Exception:
                    # Expected to fail
                    pass

                # CRITICAL: close() must be called even on exception
                mock_client.close.assert_called()

    async def test_groq_client_closed_on_success(self):
        """
        Given: parse_async() başarılı bir Groq API çağrısı yapıyor
        When: AsyncGroq client oluşturuluyor ve API çağrısı başarılı oluyor
        Then: client.close() await edilmiş olmalı (başarı sonrası)
        """
        parser = TextGenParser()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"locations": []}'))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_client.close = AsyncMock()

        with patch.object(parser, '_get_async_client', return_value=mock_client):
            with patch.object(parser, '_get_deepseek_client', return_value=AsyncMock()):
                with patch.object(parser, 'city_validator') as mock_validator:
                    mock_validator.validate_all = MagicMock(return_value={'valid': [], 'invalid': []})

                    try:
                        result = await parser.parse_async("İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON ACİL YÜK VAR TELEFON 0532 555 12 34 İLETİŞİME GEÇİNİZ LÜTFEN")
                    except Exception as e:
                        pass

                    # CRITICAL: close() must be called
                    mock_client.close.assert_called()

    async def test_groq_client_closed_on_exception(self):
        """
        Given: parse_async() Groq API çağrısı exception fırlatıyor
        When: AsyncGroq client.create() exception fırlatıyor
        Then: client.close() yine de await edilmiş olmalı (try/finally garantisi)
        """
        parser = TextGenParser()

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Rate Limited"))
        mock_client.close = AsyncMock()

        with patch.object(parser, '_get_async_client', return_value=mock_client):
            with patch.object(parser, '_get_deepseek_client', return_value=AsyncMock()):
                try:
                    result = await parser.parse_async("İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON ACİL YÜK VAR TELEFON 0532 555 12 34 İLETİŞİME GEÇİNİZ LÜTFEN")
                except Exception:
                    pass

                # CRITICAL: close() must be called even on exception
                mock_client.close.assert_called()

    async def test_all_client_types_closed_in_fallback_chain(self):
        """
        AC-3 (partial): parse_async() model fallback döngüsünde (DeepSeek -> Groq -> etc.)
        birden fazla client oluşturabilir. Her biri kapatılmalı.

        Given: DeepSeek başarısız, Groq çağrılıyor
        When: parse_async() fallback zincirinde birden fazla client oluşturuluyor
        Then: her client await client.close() çağrısından geçmeli
        """
        parser = TextGenParser()

        # First client (DeepSeek) fails
        mock_deepseek = AsyncMock()
        mock_deepseek.chat.completions.create = AsyncMock(side_effect=Exception("DeepSeek failed"))
        mock_deepseek.close = AsyncMock()

        # Second client (Groq) succeeds
        mock_groq = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"locations": []}'))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
        mock_groq.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_groq.close = AsyncMock()

        with patch.object(parser, '_get_deepseek_client', return_value=mock_deepseek):
            with patch.object(parser, '_get_async_client', return_value=mock_groq):
                with patch.object(parser, 'city_validator') as mock_validator:
                    mock_validator.validate_all = MagicMock(return_value={'valid': [], 'invalid': []})

                    try:
                        result = await parser.parse_async("İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON ACİL YÜK VAR TELEFON 0532 555 12 34 İLETİŞİME GEÇİNİZ LÜTFEN")
                    except Exception:
                        pass

                    # CRITICAL: both clients must be closed
                    mock_deepseek.close.assert_called()
                    mock_groq.close.assert_called()


@pytest.mark.asyncio
class TestClientCloseMultiThreaded:
    """AC-3: Multi-threaded scenario with asyncio.run() per thread"""

    def test_no_event_loop_closed_error_with_concurrent_workers(self):
        """
        AC-3 (full): Given eşzamanlı 5+ worker thread'i (her biri kendi asyncio.run()
        çağrısıyla), When bu senaryo testte simüle edilir, Then "RuntimeError:
        Event loop is closed" hatası oluşmamalı.

        Strategy: ThreadPoolExecutor'da 5+ task çalıştır, her biri parse_async()
        çağrısı yapıyor. Client kapatma garantisi olmadan bu scenario'da tipik
        olarak "Event loop is closed" hatası görülüyor (GC'de finalize sırasında).
        """
        parser = TextGenParser()

        async def mock_parse_task():
            """Simulates parse_async() call with mocked clients"""
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content='{"locations": []}'))]
            mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client.close = AsyncMock()

            with patch.object(parser, '_get_deepseek_client', return_value=mock_client):
                with patch.object(parser, '_get_async_client', return_value=AsyncMock()):
                    with patch.object(parser, 'city_validator') as mock_validator:
                        mock_validator.validate_all = MagicMock(return_value={'valid': [], 'invalid': []})

                        try:
                            result = await parser.parse_async("İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON ACİL YÜK VAR TELEFON 0532 555 12 34 İLETİŞİME GEÇİNİZ LÜTFEN")
                        except Exception:
                            pass

                        # Verify close was called
                        mock_client.close.assert_called()

        def thread_worker(idx):
            """Each thread runs its own event loop"""
            try:
                asyncio.run(mock_parse_task())
                return "success"
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    return f"event_loop_closed: {e}"
                raise
            except Exception as e:
                # Other exceptions are ok (API mock issues)
                return "ok"

        # Run 5 concurrent workers
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(thread_worker, range(5)))

        # Check for "Event loop is closed" errors
        event_loop_errors = [r for r in results if "event_loop_closed" in r]

        # This test EXPECTS no "Event loop is closed" errors
        # (with proper client.close() implementation)
        assert len(event_loop_errors) == 0, \
            f"Expected no 'Event loop is closed' errors, got: {event_loop_errors}"
    async def test_close_exception_does_not_propagate(self):
        """
        AC-2: client.close() exception'ı parse_async() sonucunu bozmamali.

        Given: client.close() kendisi exception fırlatıyor
        When: parse_async() başarılı bir yanıt aldı fakat close() exception fırlattı
        Then: parse_async() sonucunun başarılı olması gerekir; close error
        ayrı olarak loglanabilir (close() hatası parse sonucuna etki etmemeli)
        """
        parser = TextGenParser()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='{"locations": []}'))]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        # close() raises an exception
        mock_client.close = AsyncMock(side_effect=Exception("Close failed"))

        with patch.object(parser, '_get_deepseek_client', return_value=mock_client):
            with patch.object(parser, '_get_async_client', return_value=AsyncMock()):
                with patch.object(parser, 'city_validator') as mock_validator:
                    mock_validator.validate_all = MagicMock(return_value={'valid': [], 'invalid': []})

                    # parse_async should not fail just because close() failed
                    # (though implementation may choose to log the close error)
                    try:
                        result = await parser.parse_async("İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON ACİL YÜK VAR TELEFON 0532 555 12 34 İLETİŞİME GEÇİNİZ LÜTFEN")
                    except Exception as e:
                        # If parse_async fails, it should not be due to close() exception
                        assert "Close failed" not in str(e)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
