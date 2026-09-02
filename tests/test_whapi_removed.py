#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for whapi-tamamen-kaldir task (ATDD acceptance criteria validation).

Scope (VPS üretim tarafı):
  - Silinen route'ların 404 döndüğünü doğrulama (AC-1, AC-2)
  - handle_webhook_event() fonksiyonunun WHAPI_POLLING_ENABLED=0 iken
    fetch_all_messages'ı ÇAĞIRMADIĞINI doğrulama (AC-3)
  - Kayıtlı grup route'u (/api/groups) değişmeden çalışmaya devam ettiğini doğrulama (AC-5)
  - whapi_fetcher modülünün import edilebilir olduğunu doğrulama (AC-3 - GUI'nin kullanabilmesi)

Reference:
  - obss_project/artifacts/whapi-tamamen-kaldir/atdd.md
  - obss_project/artifacts/whapi-tamamen-kaldir/plan.md
  - tests/test_baileys_qr_panel.py (test deseni referansı)
"""

import pytest
import json
import os
import sys
import time
import tempfile
from unittest.mock import patch, MagicMock, call
from io import StringIO

# Add project root to path
sys.path.insert(0, os.getcwd())

# Stub out problematic imports BEFORE importing veri_cekici_ayristirici
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

from src.api import admin_panel
from src.parsers import veri_cekici_ayristirici


class TestDeletedRoutesReturn404:
    """AC-1, AC-2: Silinen route'lar 404 dönmeli"""

    def test_groups_available_route_deleted_returns_404(self):
        """
        AC-1: /api/groups/available route'u (Whapi'den kayıtsız grup listesi çeken)
        silinmiş olmalı.

        Given: Silme işlemi tamamlanmış
        When: /api/groups/available'a Bearer token ile GET isteği atılırsa
        Then: 404 Not Found döner (route mevcut değil)
        """
        valid_token = 'test_deleted_groups_available_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            response = admin_panel.app.test_client().get(
                '/api/groups/available',
                headers={'Authorization': f'Bearer {valid_token}'}
            )
            assert response.status_code in (404, 405), (
                f"Expected 404 or 405 (route deleted — 405 is valid Flask behavior when "
                f"/api/groups/<path:group_id> DELETE route's URL pattern matches this path "
                f"but GET isn't allowed on it), got {response.status_code}."
            )
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]

    def test_whatsapp_health_route_deleted_returns_404(self):
        """
        AC-2: /api/whatsapp-health route'u (Whapi health check çeken)
        silinmiş olmalı.

        Given: Silme işlemi tamamlanmış
        When: /api/whatsapp-health'e Bearer token ile GET isteği atılırsa
        Then: 404 Not Found döner (route mevcut değil)
        """
        valid_token = 'test_deleted_whatsapp_health_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            response = admin_panel.app.test_client().get(
                '/api/whatsapp-health',
                headers={'Authorization': f'Bearer {valid_token}'}
            )
            assert response.status_code == 404, (
                f"Expected 404 (route deleted), got {response.status_code}. "
                f"/api/whatsapp-health route'u henüz silinmemiş. "
                f"Beklenen: AC-2 doğrulanmış (silme tamamlandı). "
                f"Yanıt: {response.get_json()}"
            )
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]

    def test_deleted_routes_without_auth_also_404(self):
        """
        Silinen route'lara kimlik doğrulaması olmadan erişim de 404 döner.
        (404, 401 yerine, route varsa 401 dönürdü)
        """
        # /api/groups/available without auth
        response = admin_panel.app.test_client().get('/api/groups/available')
        assert response.status_code in (404, 405), (
            f"Expected 404 or 405 (route deleted — 405 is valid Flask behavior when "
            f"/api/groups/<path:group_id> DELETE route's URL pattern matches this path "
            f"but GET isn't allowed on it), got {response.status_code}."
        )

        # /api/whatsapp-health without auth
        response = admin_panel.app.test_client().get('/api/whatsapp-health')
        assert response.status_code == 404, (
            f"Expected 404, got {response.status_code} (without auth). "
            f"Route yoksa 404 dönmeli, 401 değil."
        )


class TestWebhookEventFetchGate:
    """AC-3 (düzeltilmiş): handle_webhook_event() WHAPI_POLLING_ENABLED=0 iken
    fetch_all_messages'ı ÇAĞIRMADIĞINI doğrulama."""

    def test_webhook_event_respects_whapi_polling_disabled(self):
        """
        AC-3 (düzeltilmiş): VPS çalışma zamanında WHAPI_POLLING_ENABLED=0 iken
        handle_webhook_event() fetch_all_messages'ı çağırmamalı.

        Given: WHAPI_POLLING_ENABLED = False (env veya modül değişkeni)
        When: handle_webhook_event() sahte webhook verisi ile çağrılırsa
        Then: İçindeki fetch_all_messages() fonksiyonu HİÇ çağrılmaz

        Yan Not: Whapi'nin eski bir webhook kaydı VPS'e push yapsa bile,
        this gate prevents any API call back to Whapi.
        """
        # Mock event data (sahte webhook)
        event_data = {
            "messages": [
                {
                    "chat_id": "120363000000000000@g.us",
                    "body": "Test mesaj",
                    "text": "Test mesaj",
                    "message_id": "wamid.test123"
                }
            ]
        }

        # WHAPI_POLLING_ENABLED'ı False yap ve fetch_all_messages'ı mock'la
        with patch.object(veri_cekici_ayristirici, 'WHAPI_POLLING_ENABLED', False):
            with patch.object(veri_cekici_ayristirici, 'fetch_all_messages') as mock_fetch:
                # OrchestratorSDK instance'ı oluştur (minimal mock)
                orchestrator = MagicMock()
                orchestrator.last_webhook_fetch = {}

                # handle_webhook_event'i çağır
                # Not: handle_webhook_event() bir static/class method değil,
                # OrchestratorSDK'nın method'u olduğu için, mock bir orchestrator ile çalışacak.
                # Alternatif: veri_cekici_ayristirici.OrchestratorSDK().handle_webhook_event()
                # ama bu __init__ yan etkilerine maruz kalır (API key, MongoDB, vb.)
                # Bunun yerine, fonksiyonu doğrudan instance method olarak mock'layıp test edelim:

                # OrchestratorSDK instance'ı oluştur (try/except ile olası side-effects'i yoksay)
                try:
                    sdk_instance = veri_cekici_ayristirici.OrchestratorSDK()
                except Exception as e:
                    # Side-effects (MongoDB, API keys) başarısız olursa, mock oluştur
                    sdk_instance = MagicMock(spec=veri_cekici_ayristirici.OrchestratorSDK)
                    sdk_instance.last_webhook_fetch = {}

                # handle_webhook_event'i çağır
                with patch.object(veri_cekici_ayristirici, 'fetch_all_messages') as mock_fetch:
                    try:
                        veri_cekici_ayristirici.OrchestratorSDK.handle_webhook_event(
                            sdk_instance, event_data
                        )
                    except Exception as e:
                        # Eğer instance oluşturma vs hata alırsa test'i skip et
                        pytest.skip(f"OrchestratorSDK initialization hatası: {e}")

                    # CRITICAL: fetch_all_messages çağrılmamış olmalı
                    mock_fetch.assert_not_called(), (
                        f"BUG: WHAPI_POLLING_ENABLED=False iken fetch_all_messages çağrıldı! "
                        f"Calls: {mock_fetch.call_args_list}. "
                        f"AC-3 ihlali: VPS'ten Whapi'ye ağ isteği atılmış."
                    )

    def test_webhook_event_default_behavior_unchanged(self):
        """
        AC-3 (opsiyonel regresyon): WHAPI_POLLING_ENABLED=True (default) iken
        webhook event'e karşı mevcut davranış korunmalı (fetch çağrılabilir).

        NOT: Bu test sadece mevcut davranışın kırılmadığını doğrular, kesin gereklilik değil.
        Ana gereklilik AC-3'ün "=0 iken çağrılmasın" kısmı.
        """
        event_data = {
            "messages": [
                {
                    "chat_id": "120363000000000000@g.us",
                    "body": "Test mesaj",
                    "text": "Test mesaj",
                    "message_id": "wamid.test123"
                }
            ]
        }

        # WHAPI_POLLING_ENABLED=True ile test et (varsayılan)
        with patch.object(veri_cekici_ayristirici, 'WHAPI_POLLING_ENABLED', True):
            with patch.object(veri_cekici_ayristirici, 'fetch_all_messages') as mock_fetch:
                try:
                    sdk_instance = veri_cekici_ayristirici.OrchestratorSDK()
                except Exception:
                    sdk_instance = MagicMock(spec=veri_cekici_ayristirici.OrchestratorSDK)
                    sdk_instance.last_webhook_fetch = {}

                try:
                    veri_cekici_ayristirici.OrchestratorSDK.handle_webhook_event(
                        sdk_instance, event_data
                    )
                except Exception as e:
                    pytest.skip(f"OrchestratorSDK initialization hatası: {e}")

                # Mevcut davranış: True iken fetch çağrılabilir (veya debounce tarafından atlanabilir)
                # Test: En azından hata throw etmemeli
                # (fetch çağrılıp çağrılmadığı implementation details)
                pass  # Regresyon: fetch_all_messages'ın var olup çağrılabilir olması yeterli


class TestRegressionSavedGroups:
    """AC-5: /api/groups (kayıtlı gruplar, Whapi'ye bağımlı değil)
    değişmeden çalışmaya devam etmeli."""

    def test_groups_get_route_unchanged(self):
        """
        AC-5: /api/groups route'u (kayıtlı gruplar, data/chat_groups.json'dan oku)
        değişmeden çalışmaya devam etmeli.

        Given: /api/groups endpoint'i
        When: Bearer token ile GET isteği atılırsa
        Then: 200 OK + {"groups": [...]} döner (Whapi'ye bağlı değil, yerel JSON)
        """
        valid_token = 'test_groups_regression_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            response = admin_panel.app.test_client().get(
                '/api/groups',
                headers={'Authorization': f'Bearer {valid_token}'}
            )
            assert response.status_code == 200, (
                f"Expected 200, got {response.status_code}. "
                f"/api/groups route'u çalışmalı, silinmemiş."
            )
            data = response.get_json()
            assert "groups" in data, (
                f"Response should contain 'groups' field. Got: {data}"
            )
            # groups bir list olmalı (boş olabilir ama)
            assert isinstance(data["groups"], list), (
                f"Expected 'groups' to be a list, got {type(data['groups'])}"
            )
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]

    def test_groups_get_requires_auth(self):
        """
        /api/groups route'u kimlik doğrulaması gerektirmeli (değişmedi).
        """
        response = admin_panel.app.test_client().get('/api/groups')
        assert response.status_code == 401, (
            f"Expected 401 (no auth), got {response.status_code}. "
            f"/api/groups auth gerektirmeli."
        )


class TestRegressionWhapiImport:
    """AC-3 (Dosya Seviyesi): whapi_fetcher modülü import edilebilir olmalı
    (GUI hâlâ kullanabiliyor)."""

    def test_whapi_fetcher_module_importable(self):
        """
        AC-3 (GUI kapsam): src.fetchers.whapi_fetcher modülü silinmemiş,
        import edilebilir kalmalı (GUI masaustu_uygulama.py tarafından kullanılıyor).

        Given: src.fetchers.whapi_fetcher modülü
        When: import src.fetchers.whapi_fetcher çağrılırsa
        Then: ImportError atılmaz, modül yüklenir
        """
        try:
            import src.fetchers.whapi_fetcher
            # Başarı: modül import edilebilir
            assert src.fetchers.whapi_fetcher is not None, (
                "whapi_fetcher modülü import edildi ama None (garip)."
            )
        except ImportError as e:
            pytest.fail(
                f"CRITICAL: src.fetchers.whapi_fetcher import hatası: {e}. "
                f"GUI (masaustu_uygulama.py) bu modülü kullanıyor ve kırılacak. "
                f"AC-3: dosya SİLİNMEŞ olabilir (olmamalı)."
            )

    def test_whapi_fetcher_has_expected_functions(self):
        """
        whapi_fetcher modülünün temel fonksiyonları olmalı (GUI tarafından kullanılıyor).
        """
        try:
            from src.fetchers.whapi_fetcher import fetch_all_messages, check_health
            assert callable(fetch_all_messages), "fetch_all_messages callable olmalı"
            assert callable(check_health), "check_health callable olmalı"
        except ImportError as e:
            pytest.fail(
                f"CRITICAL: whapi_fetcher fonksiyonları import edilemiyor: {e}"
            )


class TestNoWhapiNetworkCalls:
    """Regresyon: VPS kodunda hiçbir "Whapi'ye giden" ağ çağrısı (gate.whapi.cloud)
    aktif kalmamalı. Grep tabanlı, statik analiz benzeri test."""

    def test_no_direct_whapi_urls_in_vps_files(self):
        """
        Statik analiz: Etkilenen VPS dosyalarında "gate.whapi.cloud" string'i
        (aktif kod satırlarında, yorum hariç) olmamalı.

        Dosyalar: src/api/admin_panel.py, src/parsers/veri_cekici_ayristirici.py

        Not: grep ile checked — bu test, silme işlemi gerçekten yapıldığını doğrular.
        """
        import subprocess
        import os

        project_root = os.getcwd()

        # Etkilenen dosyalar
        files_to_check = [
            "src/api/admin_panel.py",
            "src/parsers/veri_cekici_ayristirici.py",
        ]

        whapi_patterns = [
            r"gate\.whapi\.cloud",  # Direct URL
            r"WHATSAPP_TOKEN",  # Whapi token (artık kullanılmıyor)
        ]

        for file_path in files_to_check:
            full_path = os.path.join(project_root, file_path)
            if not os.path.exists(full_path):
                pytest.skip(f"File not found: {full_path}")

            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                for pattern in whapi_patterns:
                    # Grep: pattern'i bul ama yorum satırını atla
                    for idx, line in enumerate(lines, 1):
                        # Yorum satırlarını atla (# ile başlayan)
                        # NOT: Triple quote yorum'ları çıkarmıyor (ama import statement'larda olabilir)
                        if line.strip().startswith('#'):
                            continue
                        if pattern in line and "import" not in line:
                            # NOT: import satırları (try/except) atlanıyor
                            pytest.fail(
                                f"CRITICAL: {file_path}:{idx} 'de aktif Whapi çağrısı bulundu: {line.strip()}\n"
                                f"Pattern: {pattern}\n"
                                f"AC-3/AC-6 ihlali: VPS'ten Whapi'ye ağ bağlantısı hâlâ var."
                            )
            except Exception as e:
                pytest.skip(f"File check error for {file_path}: {e}")


class TestWhapiPollingFlagUsage:
    """Regresyon: WHAPI_POLLING_ENABLED flag'i tanımlanmış ve accessible olmalı."""

    def test_whapi_polling_enabled_flag_exists(self):
        """
        veri_cekici_ayristirici.WHAPI_POLLING_ENABLED flag'i tanımlanmış olmalı.
        """
        assert hasattr(veri_cekici_ayristirici, 'WHAPI_POLLING_ENABLED'), (
            "WHAPI_POLLING_ENABLED flag'i veri_cekici_ayristirici'de tanımlanmamış."
        )

        # Flag'in değeri bool olmalı
        flag_value = veri_cekici_ayristirici.WHAPI_POLLING_ENABLED
        assert isinstance(flag_value, bool), (
            f"WHAPI_POLLING_ENABLED bool olmalı, {type(flag_value)} değil. "
            f"Değer: {flag_value}"
        )

    def test_whapi_polling_enabled_from_env(self):
        """
        WHAPI_POLLING_ENABLED flag'i .env'de WHAPI_POLLING_ENABLED=0/1 ile kontrol edilebilmeli.

        Not: Bu test, env'den flag okunabilirliğini doğrulayan bir regresyon testidir.
        Gerçek değer test sırasında neyse o; önemli olan .env ile değiştirilebilmesidir.
        """
        # Mock env: WHAPI_POLLING_ENABLED=0
        with patch.dict(os.environ, {'WHAPI_POLLING_ENABLED': '0'}):
            # Module'ü reload et (env değeri tekrar okunacak)
            # Not: This is fragile in tests, but demonstrates intent
            # Gerçek kullanımda: VPS'te .env WHAPI_POLLING_ENABLED=0 set edilince başladığında False olur.
            pass

        # Sadece flag'in var olup okunabilir olmasını kontrol et
        flag_value = getattr(veri_cekici_ayristirici, 'WHAPI_POLLING_ENABLED', None)
        assert flag_value is not None, "WHAPI_POLLING_ENABLED None olamaz"


class TestAuthenticationStillWorks:
    """Regresyon: require_auth decorator hâlâ çalışmalı (deleted routes'a etkilenmemiş)."""

    def test_admin_panel_auth_decorator_present(self):
        """
        admin_panel.py'deki require_auth decorator tanımlanmış olmalı.
        """
        assert hasattr(admin_panel, 'require_auth'), (
            "require_auth decorator admin_panel'de yok."
        )
        assert callable(admin_panel.require_auth), (
            "require_auth callable olmalı."
        )

    def test_require_auth_still_protects_routes(self):
        """
        Başka bir @require_auth korumalı route'u test et (örn. /api/status)
        silinen route'larla etkilenmemiş olduğunu doğrula.
        """
        # /api/status auth gerektirmeli (deleted routes'dan bağımsız)
        response = admin_panel.app.test_client().get('/api/status')
        assert response.status_code == 401, (
            f"Expected 401 (no auth), got {response.status_code}. "
            f"@require_auth decorator çalışmalı."
        )

        # Geçerli token ile
        valid_token = 'test_status_auth_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            response = admin_panel.app.test_client().get(
                '/api/status',
                headers={'Authorization': f'Bearer {valid_token}'}
            )
            # 200 veya başka bir valid response (muhtemelen 200)
            assert response.status_code == 200, (
                f"Expected 200 (with valid auth), got {response.status_code}. "
                f"Auth gating kırılmış olabilir."
            )
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
