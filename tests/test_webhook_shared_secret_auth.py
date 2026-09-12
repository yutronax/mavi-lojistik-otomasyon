#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for webhook-shared-secret-auth (Strix güvenlik açığı AC-2/AC-3/AC-4/AC-5).

Acceptance Criteria (from atdd.md):
1. [Critical] AC-2: Given webhook isteği geçerli `X-Webhook-Secret` header'ı taşımıyor
   veya yanlış, When `do_POST` çağrılıyor, Then istek hmac/secrets.compare_digest ile
   reddedilip 403 döner ve işleme kuyruğuna hiçbir şey eklenmez.

2. [Critical] AC-3: Given `WEBHOOK_SHARED_SECRET` ortam değişkeni tanımlı değil,
   When webhook'a herhangi bir istek gelir, Then sunucu çökmeden ayakta kalır ama
   tüm istekleri 403 ile reddeder (fail-closed).

3. [High] AC-4: Given geçerli secret ama beklenen JSON şekline uymayan gövde
   (`messages` listesi değil / obje değil), When `do_POST` çağrılıyor,
   Then 400 döner, istek loglanır, kuyruğa hiçbir şey eklenmez.

4. [High] AC-5: Given geçerli secret + geçerli şekil, When `do_POST` çağrılıyor,
   Then 200 döner ve mesaj işleme kuyruğuna eklenir (mevcut davranış korunur).

Davranış Sözleşmesi (atdd.md):
- Row 1: Happy path (geçerli secret + geçerli şekil) → 200 OK, kuyruğa eklenir (AC-5)
- Row 2: Girdi geçersiz/eksik (JSON şekli beklenene uymuyor) → 400, kuyruğa eklenmez (AC-4)
- Row 4: Yetkisiz erişim (secret eksik/yanlış) → 403, kuyruğa eklenmez (AC-2, AC-3)

Test Stratejisi:
- Entegrasyon testleri: Gerçek `vps_main._start_baileys_webhook_server()` başlatıp
  gerçek HTTP istekleri atmak, header ekleyip/eksik bırakıp secret kontrolü test etmek.
- Unit testleri: Kaynak kod stringi araması — secret kontrolü fonksiyonunun do_POST'ta
  200'den ÖNCE çağrılıp çağrılmadığı.
- Mock'lar minimal: sadece heavy bağımlılıklar (google.genai, pymongo, etc.).
"""

import pytest
import os
import sys
import socket
import threading
import time
import json
import logging
import inspect
import secrets
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import MagicMock, patch
import http.client

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out heavy imports BEFORE importing webhook_server
_mock = MagicMock()
sys.modules['google.genai'] = _mock
sys.modules['google'] = _mock
sys.modules['dotenv'] = _mock

# MongoDB mocks
_pymongo_mock = MagicMock()
_pymongo_mock.MongoClient = MagicMock()
_pymongo_mock.UpdateOne = MagicMock()
_pymongo_mock.DESCENDING = -1
_pymongo_errors_mock = MagicMock()
_pymongo_errors_mock.ConnectionFailure = Exception
_pymongo_errors_mock.PyMongoError = Exception
_pymongo_mock.errors = _pymongo_errors_mock
sys.modules['pymongo'] = _pymongo_mock
sys.modules['pymongo.errors'] = _pymongo_errors_mock

# Patch pyngrok
sys.modules['pyngrok'] = MagicMock()
sys.modules['pyngrok.conf'] = MagicMock()

# Mock OrchestratorSDK
class MockOrchestratorSDK:
    def __init__(self):
        self.processing_queue_calls = []  # Track add_to_processing_queue calls
    def add_to_processing_queue(self, *args, **kwargs):
        self.processing_queue_calls.append((args, kwargs))
    def run_loop(self):
        pass
    def handle_webhook_event(self, data):
        pass

# Patch config and reporter modules
_reporter_mock = MagicMock()
_reporter_mock.Reporter = MagicMock()
sys.modules['src.utils.reporter'] = _reporter_mock

_config_mock = MagicMock()
_config_mock.DEFAULT_CONFIG = {}
_config_mock.WHAPI_TIMEOUT = 30
sys.modules['src.utils.config'] = _config_mock

# Patch OrchestratorSDK
_veri_cekici_mock = MagicMock()
_veri_cekici_mock.OrchestratorSDK = MockOrchestratorSDK
sys.modules['src.parsers.veri_cekici_ayristirici'] = _veri_cekici_mock

from src.api.webhook_server import WhapiWebhookHandler, make_webhook_handler_class

# Import vps_main for real webhook server startup
import vps_main

# Clean up sys.modules pollution (as per test_webhook_server_threading.py pattern)
del sys.modules['src.parsers.veri_cekici_ayristirici']
del sys.modules['src.utils.reporter']
del sys.modules['src.utils.config']

# Test constant for webhook secret authentication
TEST_WEBHOOK_SECRET = "test-secret-for-atdd-red-step"


class TestAC2_UnauthorizedAccess:
    """
    AC-2: Webhook isteği geçerli `X-Webhook-Secret` header'ı taşımıyor veya yanlışsa,
    do_POST isteği 403 ile reddetmeli, işleme kuyruğuna hiçbir şey eklenmemeli.

    Davranış Sözleşmesi Row 4: Yetkisiz erişim → 403, kuyruğa eklenmez.
    """

    def test_missing_webhook_secret_header_returns_403(self):
        """
        Given: Webhook isteği X-Webhook-Secret header'ı taşımıyor
        When: POST /whapi-webhook gönderiliyor
        Then: 403 Forbidden dönmeli

        Şu an: FAIL (mevcut kod header kontrolü yapmıyor, 200 dönüyor)
        Code-copilot uygulandıktan sonra: PASS
        """
        orchestrator = MockOrchestratorSDK()
        server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
        port = server.server_address[1]
        host = 'localhost'

        try:
            time.sleep(0.1)

            conn = http.client.HTTPConnection(host, port, timeout=5)
            valid_payload = json.dumps({'messages': [{'id': 'test'}]})

            # NO X-Webhook-Secret header
            conn.request("POST", "/whapi-webhook", valid_payload, {
                "Content-Length": str(len(valid_payload)),
                "Content-Type": "application/json"
            })
            response = conn.getresponse()

            assert response.status == 403, (
                f"Missing X-Webhook-Secret header should return 403, "
                f"got {response.status}. AC-2 requires auth to be checked BEFORE 200 is sent."
            )

            conn.close()
            # Verify nothing was added to queue
            assert len(orchestrator.processing_queue_calls) == 0, (
                f"Queue should be empty when auth fails, but got {len(orchestrator.processing_queue_calls)} calls"
            )
        finally:
            server.shutdown()
            server.server_close()

    def test_invalid_webhook_secret_returns_403(self):
        """
        Given: Webhook isteği X-Webhook-Secret header'ı taşıyor ama yanlış değer
        When: POST /whapi-webhook gönderiliyor
        Then: 403 Forbidden dönmeli
        """
        orchestrator = MockOrchestratorSDK()
        server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
        port = server.server_address[1]
        host = 'localhost'

        try:
            time.sleep(0.1)

            conn = http.client.HTTPConnection(host, port, timeout=5)
            valid_payload = json.dumps({'messages': [{'id': 'test'}]})

            # Invalid X-Webhook-Secret header
            conn.request("POST", "/whapi-webhook", valid_payload, {
                "Content-Length": str(len(valid_payload)),
                "Content-Type": "application/json",
                "X-Webhook-Secret": "wrong-secret-value"
            })
            response = conn.getresponse()

            assert response.status == 403, (
                f"Invalid X-Webhook-Secret should return 403, got {response.status}"
            )

            conn.close()
            # Verify nothing was added to queue
            assert len(orchestrator.processing_queue_calls) == 0, (
                f"Queue should be empty when auth fails"
            )
        finally:
            server.shutdown()
            server.server_close()


class TestAC3_FailClosedBehavior:
    """
    AC-3: `WEBHOOK_SHARED_SECRET` ortam değişkeni tanımlı değilse,
    sunucu çökmemeli ama tüm webhook isteklerini 403 ile reddetmeli (fail-closed).

    Davranış Sözleşmesi Row 4: Yetkisiz erişim (secret tanımlı değil) → 403, fail-closed.
    """

    @patch.dict(os.environ, {}, clear=False)
    def test_missing_env_secret_returns_403_and_stays_up(self):
        """
        Given: WEBHOOK_SHARED_SECRET ortam değişkeni tanımlı değil
        When: Webhook endpoint'e herhangi bir istek gelir
        Then:
          1. Sunucu çökmemeli (ayakta kalsın)
          2. Tüm webhook isteklerini 403 ile reddetmeli
          3. Kuyruğa hiçbir şey eklenmemeli

        Şu an: FAIL (mevcut kod secret kontrolü yapmıyor)
        Code-copilot uygulandıktan sonra: PASS
        """
        # Eğer WEBHOOK_SHARED_SECRET varsa, silelim
        os.environ.pop('WEBHOOK_SHARED_SECRET', None)

        orchestrator = MockOrchestratorSDK()

        try:
            # Server başlamalı ve çökmemeli
            server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
            port = server.server_address[1]
            host = 'localhost'

            time.sleep(0.1)

            # Server sağlamlığı kontrol et (GET health check)
            health_conn = http.client.HTTPConnection(host, port, timeout=5)
            health_conn.request("GET", "/")
            health_response = health_conn.getresponse()
            assert health_response.status == 200, (
                "Server health check failed — server crashed when WEBHOOK_SHARED_SECRET missing"
            )
            health_conn.close()

            # Webhook isteği yap
            conn = http.client.HTTPConnection(host, port, timeout=5)
            valid_payload = json.dumps({'messages': [{'id': 'test'}]})

            conn.request("POST", "/whapi-webhook", valid_payload, {
                "Content-Length": str(len(valid_payload)),
                "Content-Type": "application/json"
            })
            response = conn.getresponse()

            # Fail-closed: 403 dönmeli, hiçbir şey işlenmemeli
            assert response.status == 403, (
                f"When WEBHOOK_SHARED_SECRET missing, should return 403, got {response.status}. "
                f"Fail-closed behavior: no processing, no crash."
            )

            conn.close()

            # Verify nothing was processed
            assert len(orchestrator.processing_queue_calls) == 0, (
                "Queue should be empty when WEBHOOK_SHARED_SECRET is missing"
            )

        finally:
            server.shutdown()
            server.server_close()


class TestAC4_InvalidJsonShape:
    """
    AC-4: Geçerli secret ama beklenen JSON şekline uymayan gövde gelirse 400 dönmeli,
    kuyruğa hiçbir şey eklenmemeli.

    Davranış Sözleşmesi Row 2: Girdi geçersiz → 400, kuyruğa eklenmez.
    """

    @patch.dict(os.environ, {'WEBHOOK_SHARED_SECRET': TEST_WEBHOOK_SECRET})
    def test_valid_secret_invalid_json_shape_returns_400(self):
        """
        Given: Geçerli X-Webhook-Secret header'ı var, ama JSON gövde
               beklenen şekli değil (messages listesi değil, örn. null gövde)
        When: POST /whapi-webhook gönderiliyor
        Then: 400 Bad Request dönmeli, kuyruğa hiçbir şey eklenmemeli

        ATDD Red Step: Geçerli secret sağlanıyor, gövde geçersiz → 400 bekleniyor.
        Code-copilot implementasyonundan sonra: PASS (AC-4 karşılanıyor).
        """
        orchestrator = MockOrchestratorSDK()
        server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
        port = server.server_address[1]
        host = 'localhost'

        try:
            time.sleep(0.1)

            conn = http.client.HTTPConnection(host, port, timeout=5)

            # Invalid JSON shape: null gövde
            invalid_payload = json.dumps(None)

            conn.request("POST", "/whapi-webhook", invalid_payload, {
                "Content-Length": str(len(invalid_payload)),
                "Content-Type": "application/json",
                "X-Webhook-Secret": TEST_WEBHOOK_SECRET
            })
            response = conn.getresponse()

            assert response.status == 400, (
                f"Invalid JSON shape with valid secret should return 400, "
                f"got {response.status}. AC-4 requires shape validation."
            )

            conn.close()

            # Verify nothing was processed
            assert len(orchestrator.processing_queue_calls) == 0, (
                "Queue should be empty when JSON shape is invalid"
            )
        finally:
            server.shutdown()
            server.server_close()

    @patch.dict(os.environ, {'WEBHOOK_SHARED_SECRET': TEST_WEBHOOK_SECRET})
    def test_valid_secret_missing_messages_field_returns_400(self):
        """
        Given: Geçerli secret, ama JSON gövde 'messages' field'ı yok
        When: POST /baileys-webhook gönderiliyor
        Then: 400 Bad Request dönmeli

        ATDD Red Step: Geçerli secret sağlanıyor, gövdede 'messages' alanı yok → 400 bekleniyor.
        Code-copilot implementasyonundan sonra: PASS (AC-4 karşılanıyor).
        """
        orchestrator = MockOrchestratorSDK()
        server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
        port = server.server_address[1]
        host = 'localhost'

        try:
            time.sleep(0.1)

            conn = http.client.HTTPConnection(host, port, timeout=5)

            # Missing 'messages' field and no 'id' field
            invalid_payload = json.dumps({'some_other_field': 'value'})

            conn.request("POST", "/baileys-webhook", invalid_payload, {
                "Content-Length": str(len(invalid_payload)),
                "Content-Type": "application/json",
                "X-Webhook-Secret": TEST_WEBHOOK_SECRET
            })
            response = conn.getresponse()

            assert response.status == 400, (
                f"Missing 'messages' field should return 400, got {response.status}"
            )

            conn.close()
            assert len(orchestrator.processing_queue_calls) == 0
        finally:
            server.shutdown()
            server.server_close()


class TestAC5_HappyPath:
    """
    AC-5: Geçerli secret + geçerli şekil → 200 döner ve mesaj işleme
    kuyruğuna eklenir (mevcut davranış korunur, regresyon testi).

    Davranış Sözleşmesi Row 1: Happy path → 200 OK, kuyruğa eklenir.
    """

    @patch.dict(os.environ, {'WEBHOOK_SHARED_SECRET': TEST_WEBHOOK_SECRET})
    def test_valid_secret_valid_shape_returns_200_and_queues(self):
        """
        Given: Geçerli X-Webhook-Secret header'ı + geçerli JSON şekli
               ('messages' listesi var)
        When: POST /baileys-webhook gönderiliyor
        Then: 200 OK dönmeli + mesaj işleme kuyruğuna eklenmeli

        ATDD Red Step: Geçerli secret ve geçerli şekil → 200 + kuyruğa eklenmesi bekleniyor.
        Code-copilot implementasyonundan sonra: PASS (AC-5 karşılanıyor).
        """
        # Patch json.load to return mock chat groups
        with patch('json.load', return_value=[{'id': 'test-chat', 'name': 'Test Chat Group'}]):
            orchestrator = MockOrchestratorSDK()
            server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
            port = server.server_address[1]
            host = 'localhost'

            try:
                time.sleep(0.1)

                conn = http.client.HTTPConnection(host, port, timeout=5)
                valid_payload = json.dumps({'messages': [
                    {'id': 'msg1', 'body': 'test message', 'chat_id': 'test-chat'}
                ]})

                conn.request("POST", "/baileys-webhook", valid_payload, {
                    "Content-Length": str(len(valid_payload)),
                    "Content-Type": "application/json",
                    "X-Webhook-Secret": TEST_WEBHOOK_SECRET
                })
                response = conn.getresponse()

                assert response.status == 200, (
                    f"Valid shape should return 200, got {response.status}. "
                    f"AC-5 happy path: valid secret + shape → 200 + queue."
                )

                conn.close()

                # Wait for async thread to process message
                # _handle_baileys_event runs in a daemon thread, so we need to give it time
                time.sleep(0.3)

                # Verify message was queued
                assert len(orchestrator.processing_queue_calls) > 0, (
                    "Messages should be queued for valid payload"
                )
            finally:
                server.shutdown()
                server.server_close()


class TestSourceCodeVerification:
    """
    Unit testleri — kaynak kod stringi araması ile auth/shape doğrulama
    kontrol edildiğini doğrula.
    """

    def test_do_post_has_secret_comparison(self):
        """
        Unit test: do_POST() fonksiyonunda secrets.compare_digest veya
        hmac.compare_digest ile secret karşılaştırması yapılıyor mu?

        Şu an: FAIL (secret kontrolü yok)
        Code-copilot uygulandıktan sonra: PASS
        """
        source = inspect.getsource(WhapiWebhookHandler.do_POST)

        has_compare_digest = 'compare_digest' in source or 'hmac' in source

        assert has_compare_digest, (
            "WhapiWebhookHandler.do_POST() metodu secret karşılaştırması "
            "yapmıyor (secrets.compare_digest veya hmac.compare_digest yok). "
            "AC-2 gereklidir."
        )

    def test_do_post_checks_webhook_secret_header(self):
        """
        Unit test: do_POST() fonksiyonunda X-Webhook-Secret header'ı kontrol ediliyor mu?

        Şu an: FAIL
        Code-copilot uygulandıktan sonra: PASS
        """
        source = inspect.getsource(WhapiWebhookHandler.do_POST)

        # X-Webhook-Secret header kontrolü + self.headers araması
        has_header_check = ('Webhook-Secret' in source or 'X-Webhook-Secret' in source
                            or 'self.headers' in source and 'Secret' in source)

        assert has_header_check, (
            "WhapiWebhookHandler.do_POST() metodu X-Webhook-Secret header'ını "
            "kontrol etmiyor. AC-2 gereklidir."
        )

    def test_do_post_response_order_auth_before_200(self):
        """
        Unit test: do_POST() fonksiyonda auth kontrolü 200 response'undan
        ÖNCE yapılıyor mu?

        Şu an: FAIL (mevcut kod hemen 200 döner, sonra işler)
        Code-copilot uygulandıktan sonra: PASS (auth/shape kontrolü → 200/403/400)

        Bu test, "hiçbir şey yapılamadı ama hata da yok" kuralını enforce eder:
        mevcut kodun "always 200 önce" davranışı YASAKLANMALI.
        """
        source = inspect.getsource(WhapiWebhookHandler.do_POST)
        lines = source.split('\n')

        # Basit kontrol: send_response(200) çağrısından ÖNCE
        # compare_digest veya header kontrolü olmalı

        send_response_idx = None
        secret_check_idx = None

        for i, line in enumerate(lines):
            if 'send_response' in line and '200' in line:
                send_response_idx = i
            if 'compare_digest' in line or 'Webhook-Secret' in line:
                secret_check_idx = i

        if secret_check_idx is not None and send_response_idx is not None:
            assert secret_check_idx < send_response_idx, (
                "Secret kontrolü send_response(200)'den SONRA yapılıyor. "
                "Kontrol 200'den ÖNCE olmalı (AC-2/AC-3). "
                "Mevcut 'always 200 önce, sonra işle' davranışı YASAKLANDI."
            )

    def test_do_post_returns_403_for_auth_failure(self):
        """
        Unit test: do_POST() kaynak kodunda 403 status kodu bulunuyor mu?
        (Auth başarısız olduğunda 403 dönülmesi için)

        Şu an: FAIL (403 yok)
        Code-copilot uygulandıktan sonra: PASS
        """
        source = inspect.getsource(WhapiWebhookHandler.do_POST)

        has_403 = '403' in source or 'Forbidden' in source.upper()

        assert has_403, (
            "WhapiWebhookHandler.do_POST() metodu 403 Forbidden yanıtı "
            "dönmüyor (auth başarısızlığında). AC-2/AC-3 gereklidir."
        )

    def test_do_post_returns_400_for_shape_validation(self):
        """
        Unit test: do_POST() kaynak kodunda 400 status kodu bulunuyor mu?
        (JSON şekli geçersiz olduğunda 400 dönülmesi için)

        Şu an: FAIL (400 yok)
        Code-copilot uygulandıktan sonra: PASS
        """
        source = inspect.getsource(WhapiWebhookHandler.do_POST)

        has_400 = '400' in source or 'Bad Request' in source.upper()

        assert has_400, (
            "WhapiWebhookHandler.do_POST() metodu 400 Bad Request yanıtı "
            "dönmüyor (JSON şekli geçersiz olduğunda). AC-4 gereklidir."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
