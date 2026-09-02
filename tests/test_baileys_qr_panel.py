#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for /api/whatsapp/qr endpoint (panel-baileys-qr-gosterimi).

Acceptance Criteria (atdd.md):
1. [Critical] Happy path (QR mevcut, login'li) → 200 + {"status":"need_auth","qr":"data:image/png;base64,...","generated_at":<epoch>}
2. [Critical] Oturum zaten açık → 200 + {"status":"authenticated","qr":null}
3. [High] Yetkisiz erişim (login yok) → 401 + {"error":"Yetkisiz"}
4. [High] Kaynak yok (QR dosyası hiç üretilmemiş) → 202 + {"status":"waiting","message":"..."}
5. [Medium] Dış bağımlılık hatası (QR dosyası çok eski) → 200 + {"status":"waiting",...}
6. [Medium] Kısmi başarı (QR dosyası bozuk JSON) → 200 + {"status":"waiting",...} (500 DÖNMEZ)

Test Technique:
- require_auth ile korunan route test etme: test_client() + Authorization Bearer header
- TOKENS dict'ine token yazarak geçerli bir token simüle etme: admin_panel.TOKENS[token] = time.time() + 3600
- QR dosyası yolu mock'lama: patch.object(admin_panel, 'BAILEYS_QR_PATH', <tempfile>)
- tempfile/monkeypatch kullanarak gerçek proje data/ klasörünü bozmama
"""

import pytest
import json
import os
import sys
import time
import tempfile
from unittest.mock import patch, MagicMock
from io import StringIO

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.api import admin_panel


class TestQrPanelAuth:
    """AC-3: Yetkisiz erişim (login yok) → 401"""

    def test_qr_endpoint_401_without_token(self):
        """
        Given: /api/whatsapp/qr endpoint'ine login OLMADAN istek atılır
        When: Authorization header'ı yok veya Bearer token geçersiz
        Then: 401 Unauthorized + {"error": "Yetkisiz"} döner
        """
        with patch.object(admin_panel, 'BAILEYS_QR_PATH', '/tmp/test_qr.json'):
            response = admin_panel.app.test_client().get('/api/whatsapp/qr')
            assert response.status_code == 401, f"Expected 401, got {response.status_code}"
            data = response.get_json()
            assert data.get("error") == "Yetkisiz", f"Expected error message 'Yetkisiz', got {data}"

    def test_qr_endpoint_401_with_invalid_token(self):
        """
        Given: /api/whatsapp/qr'ye geçersiz Bearer token ile istek atılır
        When: Token TOKENS dict'inde yok
        Then: 401 döner
        """
        with patch.object(admin_panel, 'BAILEYS_QR_PATH', '/tmp/test_qr.json'):
            response = admin_panel.app.test_client().get(
                '/api/whatsapp/qr',
                headers={'Authorization': 'Bearer invalid_token_123'}
            )
            assert response.status_code == 401

    def test_qr_endpoint_401_with_expired_token(self):
        """
        Given: /api/whatsapp/qr'ye geçerliyken süresi dolmuş Bearer token ile istek atılır
        When: Token TOKENS dict'inde ama expiry < time.time()
        Then: 401 döner
        """
        expired_token = 'expired_test_token_abc'
        # Token'ı geçmişte sona ermek şekilde set et
        admin_panel.TOKENS[expired_token] = time.time() - 3600  # 1 saat önce expire oldu

        try:
            with patch.object(admin_panel, 'BAILEYS_QR_PATH', '/tmp/test_qr.json'):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {expired_token}'}
                )
                assert response.status_code == 401
        finally:
            # Cleanup
            if expired_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[expired_token]


class TestQrPanelHappyPath:
    """AC-1: Happy path (QR mevcut, login'li) → 200 + {"status":"need_auth","qr":"data:image/png;base64,...","generated_at":<epoch>}"""

    def test_qr_endpoint_200_with_valid_qr_file(self):
        """
        Given: QR dosyası (data/baileys_qr.json) {"qr": "data:image/png;base64,iVBORw0...", "generated_at": <epoch>} içeriğiyle mevcut
        When: login'li bir client (/api/whatsapp/qr'ye Bearer token ile) istek attar
        Then: 200 OK + {"status": "need_auth", "qr": "data:image/png;base64,iVBORw0...", "generated_at": <epoch>} döner
        """
        # Geçerli token oluştur
        valid_token = 'test_valid_token_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600  # 1 saat sonra expire

        # Geçerli QR JSON içeriği
        qr_content = {
            "qr": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            "generated_at": int(time.time() * 1000)  # epoch milliseconds
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(qr_content, f)
                temp_qr_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                data = response.get_json()
                assert data.get("status") == "need_auth", f"Expected status 'need_auth', got {data.get('status')}"
                assert data.get("qr") is not None, "QR should not be None"
                assert data["qr"].startswith("data:image/png;base64,"), "QR should be a data URI"
                assert data.get("generated_at") is not None, "generated_at should be present"
        finally:
            # Cleanup
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)

    def test_qr_endpoint_response_structure(self):
        """
        Given: valid QR JSON file
        When: logged-in request is made
        Then: response contains required fields: status, qr, generated_at
        """
        valid_token = 'test_response_structure_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        qr_content = {
            "qr": "data:image/png;base64,test_data_uri",
            "generated_at": int(time.time() * 1000)  # epoch milliseconds
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(qr_content, f)
                temp_qr_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                data = response.get_json()
                assert "status" in data, "Response must contain 'status' field"
                assert "qr" in data, "Response must contain 'qr' field"
                assert "generated_at" in data, "Response must contain 'generated_at' field"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)


class TestQrPanelAuthenticated:
    """AC-2: Oturum zaten açık → 200 + {"status":"authenticated","qr":null}"""

    def test_qr_endpoint_authenticated_status(self):
        """
        Given: QR dosyası {"status": "authenticated"} içeriğiyle yazılmıştır (bridge.js bağlı)
        When: login'li client istek attar
        Then: 200 OK + {"status": "authenticated", "qr": null} döner
        """
        valid_token = 'test_authenticated_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        # Authenticated durum JSON'ı
        auth_content = {
            "status": "authenticated"
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(auth_content, f)
                temp_qr_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 200
                data = response.get_json()
                assert data.get("status") == "authenticated", f"Expected status 'authenticated', got {data.get('status')}"
                assert data.get("qr") is None, f"QR should be None when authenticated, got {data.get('qr')}"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)


class TestQrPanelWaiting:
    """AC-4: Kaynak yok (QR dosyası hiç üretilmemiş) → 202 + {"status":"waiting","message":"..."}"""

    def test_qr_endpoint_202_file_not_found(self):
        """
        Given: QR dosyası (data/baileys_qr.json) hiç oluşturulmamış/yoktur
        When: login'li client istek attar
        Then: 202 Accepted + {"status": "waiting", "message": "..."} döner
        """
        valid_token = 'test_waiting_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            # Non-existent file path
            with patch.object(admin_panel, 'BAILEYS_QR_PATH', '/tmp/nonexistent_qr_' + str(time.time()) + '.json'):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 202, f"Expected 202, got {response.status_code}"
                data = response.get_json()
                assert data.get("status") == "waiting", f"Expected status 'waiting', got {data.get('status')}"
                assert data.get("message") is not None, "Message should be provided"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]


class TestQrPanelOldFile:
    """AC-5: QR dosyası çok eski (>2 dk) → 200 + {"status":"waiting","message":"..."}"""

    def test_qr_endpoint_waiting_for_old_file(self):
        """
        Given: QR dosyası var ama çok eski (>2 dakika önce oluşturulmuş)
        When: login'li client istek attar
        Then: 200 OK + {"status": "waiting", "message": "..."} döner (bridge.js down olabilir uyarısı)
        """
        valid_token = 'test_old_file_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        # QR dosyası 3 dakika önceki timestamp ile
        old_timestamp = int((time.time() - 180) * 1000)  # 3 minutes ago in ms
        qr_content = {
            "qr": "data:image/png;base64,old_qr_data",
            "generated_at": old_timestamp
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(qr_content, f)
                temp_qr_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 200
                data = response.get_json()
                assert data.get("status") == "waiting", f"Expected status 'waiting' for old file, got {data.get('status')}"
                assert data.get("message") is not None, "Message should explain age issue"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)


class TestQrPanelBrokenJson:
    """AC-6: QR dosyası bozuk JSON → 200 + {"status":"waiting","message":"..."} (500 DÖNMEZ)"""

    def test_qr_endpoint_broken_json_not_500(self):
        """
        Given: QR dosyası bozuk/geçersiz JSON içeriği (parse error)
        When: login'li client istek attar
        Then: 200 OK + {"status": "waiting", "message": "..."} döner (hata yutulur, 500 DÖNMEZ)
        """
        valid_token = 'test_broken_json_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                # Write broken JSON
                f.write('{ "qr": "incomplete_data", "generated_at": ')
                temp_qr_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                # CRITICAL: Should NOT be 500
                assert response.status_code != 500, f"Broken JSON should not cause 500, got {response.status_code}"
                assert response.status_code in [200, 202], f"Should return 200 or 202, got {response.status_code}"

                data = response.get_json()
                assert data.get("status") in ["waiting", "error"], f"Should return safe status, got {data.get('status')}"
                # Panel should not crash
                assert response.data is not None, "Response data should not be None"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)

    def test_qr_endpoint_non_numeric_generated_at_not_500(self):
        """
        Given: data/baileys_qr.json sözdizimsel olarak geçerli JSON ama generated_at sayısal DEĞİL (örn. string)
        When: login'li client istek atar
        Then: 500 DÖNMEZ, "waiting" durumuna düşürülür (atdd.md Davranış Sözleşmesi satır 7)
        """
        valid_token = 'test_non_numeric_generated_at_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        qr_content = {
            "qr": "data:image/png;base64,test",
            "generated_at": "bozuk_string_deger"  # String instead of numeric
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(qr_content, f)
                temp_qr_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                # CRITICAL: Should NOT be 500
                assert response.status_code != 500, f"Non-numeric generated_at should not cause 500, got {response.status_code}"
                data = response.get_json()
                assert data.get("status") == "waiting", f"Expected status 'waiting', got {data.get('status')}"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)

    def test_qr_endpoint_empty_file(self):
        """
        Given: QR dosyası boş
        When: login'li client istek attar
        Then: 200/202 + "waiting" status döner (500 DÖNMEZ)
        """
        valid_token = 'test_empty_file_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write('')  # Empty file
                temp_qr_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code != 500
                assert response.status_code in [200, 202]
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)


class TestQrPanelEdgeCases:
    """Edge case tests"""

    def test_qr_endpoint_with_malformed_bearer_header(self):
        """
        Given: Authorization header'ı "Bearer " ama token boş/eksik
        When: /api/whatsapp/qr'ye istek atılır
        Then: 401 döner
        """
        with patch.object(admin_panel, 'BAILEYS_QR_PATH', '/tmp/test_qr.json'):
            response = admin_panel.app.test_client().get(
                '/api/whatsapp/qr',
                headers={'Authorization': 'Bearer'}  # Malformed
            )
            assert response.status_code == 401

    def test_qr_endpoint_with_wrong_auth_scheme(self):
        """
        Given: Authorization header'ı "Basic" veya başka scheme'i kullanıyor
        When: /api/whatsapp/qr'ye istek atılır
        Then: 401 döner
        """
        with patch.object(admin_panel, 'BAILEYS_QR_PATH', '/tmp/test_qr.json'):
            response = admin_panel.app.test_client().get(
                '/api/whatsapp/qr',
                headers={'Authorization': 'Basic dXNlcjpwYXNz'}
            )
            assert response.status_code == 401

    def test_qr_endpoint_method_not_allowed(self):
        """
        Given: /api/whatsapp/qr'ye POST isteği atılır (GET olmadan)
        When: Endpoint sadece GET'i desteklerse
        Then: 405 Method Not Allowed döner
        """
        valid_token = 'test_method_not_allowed_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            with patch.object(admin_panel, 'BAILEYS_QR_PATH', '/tmp/test_qr.json'):
                response = admin_panel.app.test_client().post(
                    '/api/whatsapp/qr',
                    headers={'Authorization': f'Bearer {valid_token}'},
                    json={}
                )
                # Should be either 405 or route not found (404 is also acceptable if route is GET-only)
                assert response.status_code in [404, 405], f"Expected 404/405, got {response.status_code}"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
