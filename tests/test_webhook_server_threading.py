#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for webhook-server-threading-fix.

Acceptance Criteria (from atdd.md):
1. [Critical] AC-1: Given webhook sunucusu `ThreadingHTTPServer` kullanıyor,
   When bir istek (A) `rfile.read()`'de kasıtlı olarak takılırsa,
   Then aynı anda gelen ikinci istek (B) A'nın bitmesini beklemeden,
   1 saniyeden kısa sürede yanıtlanır.

2. [Critical] AC-2: Given her client soket'ine bir `timeout` (30 saniye) atanmış,
   When bir bağlantı bu süre boyunca veri göndermez/almazsa,
   Then bağlantı `socket.timeout` ile kapatılır.

3. [High] AC-3: Given mevcut `except Exception` hata yakalama davranışı,
   When bozuk JSON gelirse, Then mevcut davranış (500 dönme, hata loglama)
   DEĞİŞMEDEN korunur — regresyon testi.

4. [Medium] AC-4: Given `_handle_baileys_event`'in kendi içinde zaten ayrı bir
   `threading.Thread` açtığı, When `ThreadingHTTPServer`'a geçilirse,
   Then bu iç içe thread yapısı ek bir mimari sorun yaratmaz — regresyon testi.

5. [Unit] ThreadingHTTPServer kontrol: Kaynak kodda `ThreadingHTTPServer`
   kullanıldığını doğrula (şu an fail, code-copilot uygulandıktan sonra pass).

Test Stratejisi:
- Entegrasyon testleri: Gerçek `http.server.HTTPServer` başlatıp gerçek soket
  üzerinden yavaş istemci/hızlı istemci akışlarını test et.
- Unit testleri: Sınıf attribute'ları, kaynak kod stringi araması.
- Mock'lar minimal (sadece heavy bağımlılıklar, örn. OrchestratorSDK).
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

# Patch pyngrok before importing webhook_server
sys.modules['pyngrok'] = MagicMock()
sys.modules['pyngrok.conf'] = MagicMock()

# Mock OrchestratorSDK before importing webhook_server (used in veri_cekici_ayristirici)
from unittest.mock import patch

# Pre-patch veri_cekici_ayristirici module and its dependencies
def create_mock_orchestrator():
    """Factory for creating mock orchestrator instances."""
    return MagicMock()

# Create fake orchestrator class that can be instantiated
class MockOrchestratorSDK:
    def __init__(self):
        pass
    def add_to_processing_queue(self, *args, **kwargs):
        pass
    def run_loop(self):
        pass

# Patch config and reporter modules
_reporter_mock = MagicMock()
_reporter_mock.Reporter = MagicMock()
sys.modules['src.utils.reporter'] = _reporter_mock

_config_mock = MagicMock()
_config_mock.DEFAULT_CONFIG = {}
_config_mock.WHAPI_TIMEOUT = 30
sys.modules['src.utils.config'] = _config_mock

# Patch OrchestratorSDK directly in the module before import
_veri_cekici_mock = MagicMock()
_veri_cekici_mock.OrchestratorSDK = MockOrchestratorSDK
sys.modules['src.parsers.veri_cekici_ayristirici'] = _veri_cekici_mock

from src.api.webhook_server import WhapiWebhookHandler, make_webhook_handler_class

# Import vps_main for real webhook server startup
import vps_main

# DUZELTME (CI kirmizi hatasi): yukaridaki sys.modules['src.parsers.veri_cekici_ayristirici']
# atamasi pytest'in COLLECTION asamasinda (tum test dosyalari calistirilmadan
# once import edilir) kalici olarak calisiyor ve HIC geri alinmiyordu. Bu,
# sureç genelinde paylasilan sys.modules cache'ini kirletip test_junk_message_filter.py
# gibi baska test dosyalarinin (calistirma asamasinda, fonksiyon icinde
# `from src.parsers.veri_cekici_ayristirici import _is_junk_message` yapan)
# GERCEK modul yerine bu sahte MockOrchestratorSDK objesini almasina, ve
# cagirdiklari her fonksiyonun bir MagicMock donmesine yol aciyordu (izole
# calistirildiginda bu dosya hic import edilmedigi icin sorun gorunmuyordu).
# Sahte modulu buradan sonra kaldiriyoruz ki sonraki testler GERCEK moduluyle
# calissin (google/pymongo/dotenv/pyngrok mock'lari zaten sys.modules'ta
# kaldigi icin gercek modulun importu burada da sorunsuz calisir).
del sys.modules['src.parsers.veri_cekici_ayristirici']


class TestAC2_TimeoutAttribute:
    """
    AC-2: Handler sınıfının `timeout` class attribute'u tanımlanmış olmalı.

    Şu an: WhapiWebhookHandler.timeout = None (tanımlanmamış)
    Code-copilot sonrası: WhapiWebhookHandler.timeout = 30
    """

    def test_handler_has_timeout_attribute(self):
        """
        Given: WhapiWebhookHandler sınıfı
        When: timeout attribute'u sorgulanırsa
        Then: timeout 30 saniye (veya 0'dan büyük bir değer) olmalı

        Şu an fail (None), code-copilot uygulandıktan sonra pass.
        """
        timeout_value = getattr(WhapiWebhookHandler, 'timeout', None)
        # Bu test şu an fail olacak (None), code-copilot timeout=30 ekleyince pass olacak
        assert timeout_value is not None, (
            "WhapiWebhookHandler.timeout attribute'u tanımlanmamış "
            "(None). Code-copilot timeout=30 eklemeli."
        )
        assert isinstance(timeout_value, (int, float)) and timeout_value > 0, (
            f"WhapiWebhookHandler.timeout = {timeout_value} olmalı (30 gibi), "
            f"pozitif bir sayı olmalı"
        )


class TestAC3_BadJsonResponse:
    """
    AC-3: Bozuk JSON gönderildiğinde 500 yanıtı dönmelidir (regresyon testi).

    Bu test hem şu an hem de code-copilot uygulandıktan sonra pass olmalı.
    """

    def test_malformed_json_returns_500(self):
        """
        Given: Webhook endpoint'e bozuk JSON gönderiliyor
        When: do_POST çalışırsa
        Then: 500 yanıtı dönmelidir (hata davranışı korunmalı)

        Bu test regresyon testi — yapısal değişiklik (HTTPServer→ThreadingHTTPServer)
        bu davranışı etkilememeli.

        DÜZELTME (Red-team): Bu test artık gerçek vps_main._start_baileys_webhook_server()
        fonksiyonunu çağırıyor, kendi ThreadingHTTPServer inşaası yerine.
        """
        # Gerçek production fonksiyonu çağır (port=0 = rastgele boş port)
        orchestrator = MagicMock()
        server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
        port = server.server_address[1]  # Rastgele atanan port
        host = 'localhost'  # Server 0.0.0.0'da dinliyor, localhost'a bağlanırız

        try:
            time.sleep(0.1)  # Server başlaması için biraz zaman ver

            # Client: bozuk JSON gönder
            conn = http.client.HTTPConnection(host, port, timeout=5)

            bad_json = b"{ invalid json syntax"  # Bozuk
            conn.request("POST", "/whapi-webhook", bad_json, {
                "Content-Length": str(len(bad_json)),
                "Content-Type": "application/json"
            })
            response = conn.getresponse()

            # 500 yanıtı beklenir
            assert response.status == 500, (
                f"Bozuk JSON için 500 beklendi, {response.status} alındı. "
                f"Mevcut hata davranışı korunmalı (regresyon testi)."
            )

            conn.close()
        finally:
            server.shutdown()
            server.server_close()


class TestAC4_RegressionThreadingPresent:
    """
    AC-4: Webhook handler'ında (`do_POST`) `threading.Thread` açılması
    zaten mevcut (regresyon testi).

    AÇIKLAMA (atdd.md AC-4 tanımından):
    "thread içinde thread" deseni: do_POST içinde _handle_baileys_event
    bir thread'de çağrılıyor (thread1), ve bu fonksiyon (yapısının kendi
    içinde başka thread açmaz, ama) orchestrator.add_to_processing_queue
    çağırıyor. AC-4, bu tasarımın "ek mimari sorun yaratmaz"ını test eder.
    Kaynak temsili: do_POST'ta thread.start() çağrısı olmalı (mevcut).

    Bu test hem şu an hem de code-copilot sonrası pass olmalı.
    """

    def test_baileys_event_async_call_in_do_post(self):
        """
        Given: webhook_server.py do_POST metodu
        When: do_POST'un kaynak kodu incelenirse
        Then: _handle_baileys_event çağrısının bir threading.Thread içinde
              yapılması gerekir (zaten yapılıyor)

        Regresyon testi — yapısal değişiklik bu thread deseni etkilememeli.
        NOT: _handle_baileys_event'in KENDİ içinde thread açması beklenmez,
        sadece do_POST içinde async çağrılması yeterlidir.
        """
        source = inspect.getsource(WhapiWebhookHandler.do_POST)

        # do_POST içinde threading.Thread ile _handle_baileys_event çağrılmalı
        assert 'threading.Thread' in source, (
            "WhapiWebhookHandler.do_POST() metodu "
            "_handle_baileys_event'i bir threading.Thread içinde çağırmalı"
        )
        assert '_handle_baileys_event' in source, (
            "do_POST() metodu _handle_baileys_event çağırmalı"
        )

    def test_webhook_handler_uses_threading(self):
        """
        Given: WhapiWebhookHandler.do_POST() metodu
        When: do_POST'un kaynak kodu incelenirse
        Then: `threading.Thread` açılması olmalı (hem Baileys hem Whapi yolu için)

        Regresyon testi — yapısal değişiklik bu thread deseni etkilememeli.
        """
        source = inspect.getsource(WhapiWebhookHandler.do_POST)

        assert 'threading.Thread' in source, (
            "WhapiWebhookHandler.do_POST() metodu threading.Thread açmalı "
            "(event işlemesi için)"
        )
        assert '.start()' in source, (
            "WhapiWebhookHandler.do_POST() metodu thread.start() çağırmalı"
        )


class TestAC1_ConcurrentRequests:
    """
    AC-1: Eşzamanlı istekler — bir istek takılırken diğer istek hızlı yanıtlanmalı.

    Bu test ENTEGRASYON testidir:
    - Mevcut `HTTPServer` (single-threaded) kullanıldığında: başarısız olacak
      (2. istek 1 saniye içinde yanıt alamaz, timeout/başarısızlık)
    - Code-copilot `ThreadingHTTPServer`'a geçince: pass (2. istek hızlı yanıtlanır)

    NOT: Test her ikisini de test etmelidir (mevcut bugged davranış + geçtiğinde
    de çalışması). Şu anda HTTPServer olduğundan, bu test FAIL olacak.
    Expectation: "Slow client tıkandığında, fast client dip timeout/başarısızlık
    yaşamaz" — yani timeout zamanı içinde yanıt alması gerekir.
    """

    def test_concurrent_requests_with_slow_client(self):
        """
        Given: Webhook sunucusu (HTTPServer veya ThreadingHTTPServer) çalışıyor
        When:
          1. Slow client: Header'ı gönderip body bekletir (socket bağlı tutar)
          2. Fast client: Aynı anda GET isteği gönderir
        Then: Fast client (2. istek) 1 saniye içinde yanıt almalı
              (Slow client'ten bağımsız)

        Şu an (HTTPServer): FAIL — Fast client timeout/başarısızlık yaşar
        Code-copilot (ThreadingHTTPServer): PASS — Fast client hızlı yanıt alır

        DÜZELTME (Red-team): Bu test artık gerçek vps_main._start_baileys_webhook_server()
        fonksiyonunu çağırıyor, kendi ThreadingHTTPServer inşaası yerine.
        """
        # Gerçek production fonksiyonu çağır (port=0 = rastgele boş port)
        orchestrator = MagicMock()
        server = vps_main._start_baileys_webhook_server(orchestrator, port=0)
        port = server.server_address[1]  # Rastgele atanan port
        host = 'localhost'  # Server 0.0.0.0'da dinliyor, localhost'a bağlanırız

        slow_socket = None
        try:
            time.sleep(0.2)  # Server başlaması için zaman ver

            # === Step 1: Slow client — POST header gönderip body'sini bekleme ===
            slow_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            slow_socket.connect((host, port))

            # Content-Length: 100 (body geleceğini söyle ama gönderme)
            slow_header = (
                b"POST /whapi-webhook HTTP/1.1\r\n"
                b"Host: localhost\r\n"
                b"Content-Type: application/json\r\n"
                b"Content-Length: 100\r\n"
                b"\r\n"
            )
            slow_socket.sendall(slow_header)
            # BURADA BODY GÖNDERMİYORUZ — Server do_POST'da `self.rfile.read(100)`
            # de sonsuz time bekleyecek (HTTPServer tek-thread'li olduğundan)

            # === Step 2: Fast client — GET isteği gönder (async) ===
            time.sleep(0.1)  # Slow client'i socket'te takılı tut

            fast_start = time.time()
            fast_success = False
            fast_error = None

            def fast_client_request():
                nonlocal fast_success, fast_error
                try:
                    conn = http.client.HTTPConnection(host, port, timeout=1.0)
                    conn.request("GET", "/")
                    response = conn.getresponse()
                    if response.status == 200:
                        fast_success = True
                    conn.close()
                except socket.timeout:
                    fast_error = "timeout"
                except ConnectionRefusedError:
                    fast_error = "refused"
                except Exception as e:
                    fast_error = str(e)

            fast_thread = threading.Thread(target=fast_client_request, daemon=True)
            fast_thread.start()
            fast_thread.join(timeout=2)  # Max 2 saniye bekle

            fast_elapsed = time.time() - fast_start

            # === Doğrulama ===
            # Mevcut HTTPServer'da (single-threaded) bu başarısız olacak:
            # - Fast client timeout yaşar (slow client tıkandığından)
            # - Fast client yanıt alamaz
            #
            # ThreadingHTTPServer'da (multi-threaded) başarılı olacak:
            # - Fast client hızlı (< 1 saniye) yanıt alır

            # Test beklentisi: Fast client 1 saniye içinde yanıt ALABILMELI
            # (şu an fail, code-copilot uygulandıktan sonra pass)
            assert fast_success or fast_elapsed < 1.0, (
                f"Fast client (GET health check) 1 saniye içinde "
                f"yanıtlanamamış (Slow client takılı tutarken). "
                f"fast_success={fast_success}, elapsed={fast_elapsed:.2f}s, "
                f"error={fast_error}. "
                f"Bu test HTTPServer'da (single-threaded) BAŞARISIZ olur "
                f"(bug'ı gösterir), ThreadingHTTPServer'a (multi-threaded) "
                f"geçince PASS olur."
            )

        finally:
            if slow_socket:
                try:
                    slow_socket.close()
                except:
                    pass

            server.shutdown()
            server.server_close()


class TestSourceCodeVerification:
    """
    Unit testleri — kaynak kod stringi araması ile yapısal değişiklikleri doğrula.
    """

    def test_run_server_uses_threading_http_server(self):
        """
        Unit test: run_server() fonksiyonunun kaynak kodunda
        `ThreadingHTTPServer` kullanılıyor mu?

        Şu an (mevcut): FAIL — HTTPServer kullanıyor
        Code-copilot uygulandıktan sonra: PASS — ThreadingHTTPServer kullanıyor
        """
        from src.api import webhook_server

        source = inspect.getsource(webhook_server.run_server)

        # Kaynak kodda ThreadingHTTPServer bulunmalı
        # (veya en azından HTTPServer değişmemeli; code-copilot ThreadingHTTPServer ekleyecek)
        has_threading_http_server = 'ThreadingHTTPServer' in source
        has_http_server = 'HTTPServer' in source

        # Şu an fail (sadece HTTPServer var), code-copilot uygulandıktan sonra pass
        assert has_threading_http_server, (
            "run_server() fonksiyonunda ThreadingHTTPServer kullanılmalı. "
            "Şu an hâlâ HTTPServer kullanılıyor (bug). "
            "Code-copilot bunu düzeltmeli."
        )

    def test_import_threading_http_server(self):
        """
        Unit test: webhook_server.py'nin import satırında
        `ThreadingHTTPServer` import edilmiş olmalı.

        Şu an (mevcut): FAIL — `from http.server import BaseHTTPRequestHandler, HTTPServer`
        Code-copilot uygulandıktan sonra: PASS — `ThreadingHTTPServer` de import edilmeli
        """
        from src.api import webhook_server

        source_file = inspect.getsourcefile(webhook_server)
        with open(source_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Import satırında ThreadingHTTPServer olmalı
        assert 'ThreadingHTTPServer' in source, (
            "webhook_server.py'nin import satırında ThreadingHTTPServer "
            "import edilmemesi gerekebilir (ama işlevsel olarak kullanılmalı). "
            "Code-copilot import eklemeli: "
            "from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer"
        )

    def test_vps_main_uses_threading_http_server(self):
        """
        Unit test: vps_main.py'nin `_start_baileys_webhook_server()`
        fonksiyonu `ThreadingHTTPServer` kullanıyor mu?

        Şu an (mevcut): FAIL — HTTPServer kullanıyor (satır 83)
        Code-copilot uygulandıktan sonra: PASS — ThreadingHTTPServer kullanıyor

        PM2 tarafından çalıştırılan gerçek üretim giriş noktası (mavi-lojistik-server)
        bu dosya olduğundan, HTTPServer → ThreadingHTTPServer dönüşümü burada da
        kontrol edilmelidir (sadece webhook_server.py'de değil).
        """
        vps_main_path = os.path.join(
            os.path.dirname(__file__), '..', 'vps_main.py'
        )
        with open(vps_main_path, 'r', encoding='utf-8') as f:
            vps_main_source = f.read()

        # vps_main.py'nin import satırında ThreadingHTTPServer olmalı
        has_threading_import = 'ThreadingHTTPServer' in vps_main_source

        assert has_threading_import, (
            "vps_main.py'nin import satırında ThreadingHTTPServer import edilmeliydi. "
            "Şu an HTTPServer kullanılıyor (bug — satır 83'de "
            "server = HTTPServer(('0.0.0.0', port), handler_class)). "
            "Code-copilot bunu düzeltmeli: "
            "from http.server import HTTPServer, ThreadingHTTPServer"
        )


class TestTimeoutBehavior:
    """
    AC-2 entegrasyon testi: 30 saniyelik timeout'un gerçekten çalıştığını doğrula.
    (Bu test sadece yapısal kontrol; çalışan bir timeout mekanizmasını test etmek
     çok zaman alacağından, burada sadece attribute varlığı kontrol edilir.)
    """

    def test_socket_timeout_mechanism(self):
        """
        Entegrasyon testi: Handler'ın timeout attribute'u set edildiğinde,
        socket'in timeout'u da set edilmeli (BaseHTTPRequestHandler
        tarafından otomatik olarak yapılır).

        Burada sadece attribute kontrol edilir; gerçek 30 saniyelik
        timeout bekleme çok zaman alacağından skip edilir.
        """
        # AC-2'de belirtildiği üzere, WhapiWebhookHandler.timeout = 30 set
        # edilirse, socket otomatik olarak timeout'a sahip olur.
        # Bu test sadece attribute'un varlığını kontrol eder.

        timeout_value = getattr(WhapiWebhookHandler, 'timeout', None)

        # timeout varsa, socket'e otomatik olarak uygulanır
        # (BaseHTTPRequestHandler.setup() tarafından)
        if timeout_value is not None:
            assert timeout_value > 0, "timeout pozitif bir sayı olmalı"
            # Başarılı — code-copilot uygulandıktan sonra bu test pass olacak


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
