#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for /api/whatsapp/groups endpoint (baileys-grup-listesi).

Acceptance Criteria (atdd.md):
1. [Critical] Happy path (bridge periyodik tarama yaptı, panel okuyor) → 200 + {"groups":[...],"cached":true}
2. [Critical] Baileys bağlı değil (data/baileys_qr.json'daki status "authenticated" değilse) → 202 + {"groups":[],"message":"..."}
3. [High] Kaynak yok (data/baileys_groups.json hiç yok) → 202 + {"groups":[],"message":"..."}
4. [Medium] Yetkisiz erişim (login yok) → 401 + {"error":"Yetkisiz"} (mevcut require_auth deseni)
5. [Medium] Dış bağımlılık hatası (bridge.js hata verirse) → Bridge.js tarafında log'a düşer, dosya bozulmaz. Panel bir önceki veriyi gösterir
6. [Medium] Kısmi başarı (dosya var ama bozuk JSON) → 200 + {"groups":[],"cached":false} (500 DEĞİL)
7. [Low] "saved" alanının doğru hesaplandığını doğrulayan test (data/chat_groups.json'daki mevcut kayıtlarla karşılaştırma)

Test Technique:
- require_auth ile korunan route test etme: test_client() + Authorization Bearer header
- TOKENS dict'ine token yazarak geçerli bir token simüle etme: admin_panel.TOKENS[token] = time.time() + 3600
- Dosya yolu mock'lama: patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', <tempfile>) ve patch.object(admin_panel, 'BAILEYS_QR_PATH', <tempfile>)
- tempfile/monkeypatch kullanarak gerçek proje data/ klasörünü bozmama

Davranış Sözleşmesi Tablosundan Hedeflenen Testler:
1. Happy path (bridge periyodik tarama yaptı, panel okuyor) → AC-1, AC-2
2. Baileys bağlı değil → AC-3
3. Kaynak yok (dosya hiç yok, ilk tarama bekleniyor) → AC-4
4. Yetkisiz erişim → mevcut require_auth deseni (ayrı AC gerekmiyor)
5. Dış bağımlılık hatası (bridge.js hata verirse) → AC-5
6. Kısmi başarı (dosya var ama bozuk JSON) → AC-6
7. "saved" alanının doğru hesaplanması → AC-2
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


class TestGroupsPanelAuth:
    """AC-4: Yetkisiz erişim (login yok) → 401"""

    def test_groups_endpoint_401_without_token(self):
        """
        Given: /api/whatsapp/groups endpoint'ine login OLMADAN istek atılır
        When: Authorization header'ı yok veya Bearer token geçersiz
        Then: 401 Unauthorized + {"error": "Yetkisiz"} döner
        """
        with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', '/tmp/test_groups.json'):
            response = admin_panel.app.test_client().get('/api/whatsapp/groups')
            assert response.status_code == 401, f"Expected 401, got {response.status_code}"
            data = response.get_json()
            assert data.get("error") == "Yetkisiz", f"Expected error message 'Yetkisiz', got {data}"

    def test_groups_endpoint_401_with_invalid_token(self):
        """
        Given: /api/whatsapp/groups'a geçersiz Bearer token ile istek atılır
        When: Token TOKENS dict'inde yok
        Then: 401 döner
        """
        with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', '/tmp/test_groups.json'):
            response = admin_panel.app.test_client().get(
                '/api/whatsapp/groups',
                headers={'Authorization': 'Bearer invalid_token_123'}
            )
            assert response.status_code == 401

    def test_groups_endpoint_401_with_expired_token(self):
        """
        Given: /api/whatsapp/groups'a geçerliyken süresi dolmuş Bearer token ile istek atılır
        When: Token TOKENS dict'inde ama expiry < time.time()
        Then: 401 döner
        """
        expired_token = 'expired_groups_token_abc'
        # Token'ı geçmişte sona ermek şekilde set et
        admin_panel.TOKENS[expired_token] = time.time() - 3600  # 1 saat önce expire oldu

        try:
            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', '/tmp/test_groups.json'):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {expired_token}'}
                )
                assert response.status_code == 401
        finally:
            # Cleanup
            if expired_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[expired_token]


class TestGroupsPanelHappyPath:
    """AC-1, AC-2: Happy path (bridge periyodik tarama yaptı, panel okuyor) → 200 + {"groups":[...],"cached":true}"""

    def test_groups_endpoint_200_with_valid_groups_file(self):
        """
        Given: groups dosyası (data/baileys_groups.json) {"groups": [{"id": "...", "name": "..."}, ...]} içeriğiyle mevcut
        When: login'li bir client (/api/whatsapp/groups'a Bearer token ile) istek attar
        Then: 200 OK + {"groups": [...], "cached": true} döner
        """
        # Geçerli token oluştur
        valid_token = 'test_valid_token_groups_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600  # 1 saat sonra expire

        # Geçerli groups JSON içeriği (bridge.js tarafından yazılacak format)
        groups_content = {
            "groups": [
                {"id": "120363024125432@g.us", "name": "Test Grubu 1", "saved": False},
                {"id": "120363025987654@g.us", "name": "Test Grubu 2", "saved": True},
            ]
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(groups_content, f)
                temp_groups_path = f.name

            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                data = response.get_json()
                assert "groups" in data, f"Expected 'groups' field in response"
                assert "cached" in data, f"Expected 'cached' field in response"
                assert data.get("cached") is True, f"Expected cached=true, got {data.get('cached')}"
                assert len(data.get("groups", [])) > 0, "Expected at least one group"
        finally:
            # Cleanup
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)

    def test_groups_endpoint_response_structure(self):
        """
        Given: valid groups JSON file
        When: logged-in request is made
        Then: response contains required fields: groups (array), cached (bool)
        """
        valid_token = 'test_response_structure_groups_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        groups_content = {
            "groups": [
                {"id": "120363024125432@g.us", "name": "Test Grubu", "saved": False},
            ]
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(groups_content, f)
                temp_groups_path = f.name

            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                data = response.get_json()
                assert "groups" in data, "Response must contain 'groups' field"
                assert "cached" in data, "Response must contain 'cached' field"
                assert isinstance(data.get("groups"), list), "'groups' should be a list"
                assert isinstance(data.get("cached"), bool), "'cached' should be a boolean"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)

    def test_groups_have_id_and_name_fields(self):
        """
        Given: groups dosyasında {"id": ..., "name": ...} şeklinde kayıtlar
        When: /api/whatsapp/groups çağrılır
        Then: her grup objekti id ve name alanlarını içerir
        """
        valid_token = 'test_group_fields_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        groups_content = {
            "groups": [
                {"id": "120363024125432@g.us", "name": "Lojistik Grubu", "saved": False},
                {"id": "120363025987654@g.us", "name": "Yönetim Grubu", "saved": True},
            ]
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(groups_content, f)
                temp_groups_path = f.name

            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 200
                data = response.get_json()
                for group in data.get("groups", []):
                    assert "id" in group, "Each group must have 'id' field"
                    assert "name" in group, "Each group must have 'name' field"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)


class TestGroupsPanelNotAuthenticated:
    """AC-3: Baileys bağlı değil (need_auth/waiting durumunda) → 202 + {"groups": [], "message": "..."}"""

    def test_groups_endpoint_202_baileys_not_authenticated(self):
        """
        Given: Baileys bağlı değil (data/baileys_qr.json'daki status "authenticated" değil)
        When: login'li client /api/whatsapp/groups'a istek attar
        Then: 202 Accepted + {"groups": [], "message": "WhatsApp henüz bağlı değil"} döner
        """
        valid_token = 'test_not_auth_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        # Baileys bağlı değil (status != "authenticated")
        qr_content = {
            "qr": "data:image/png;base64,test_qr_data",
            "generated_at": int(time.time() * 1000)
        }

        groups_content = {
            "groups": [
                {"id": "120363024125432@g.us", "name": "Test Grubu", "saved": False},
            ]
        }

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(qr_content, f)
                temp_qr_path = f.name

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(groups_content, f)
                temp_groups_path = f.name

            with patch.object(admin_panel, 'BAILEYS_QR_PATH', temp_qr_path):
                with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                    response = admin_panel.app.test_client().get(
                        '/api/whatsapp/groups',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    assert response.status_code == 202, f"Expected 202, got {response.status_code}"
                    data = response.get_json()
                    assert data.get("groups") == [], f"Expected empty groups, got {data.get('groups')}"
                    assert data.get("message") is not None, "Expected message field"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_qr_path):
                os.unlink(temp_qr_path)
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)


class TestGroupsPanelNoSource:
    """AC-4: Kaynak yok (dosya hiç yok, ilk tarama bekleniyor) → 202 + {"groups": [], "message": "..."}"""

    def test_groups_endpoint_202_file_not_found(self):
        """
        Given: groups dosyası (data/baileys_groups.json) hiç oluşturulmamış/yoktur
        When: login'li client /api/whatsapp/groups'a istek attar
        Then: 202 Accepted + {"groups": [], "message": "Gruplar henüz taranmadı..."} döner
        """
        valid_token = 'test_no_source_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            # Non-existent file path
            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', '/tmp/nonexistent_groups_' + str(time.time()) + '.json'):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 202, f"Expected 202, got {response.status_code}"
                data = response.get_json()
                assert data.get("groups") == [], f"Expected empty groups, got {data.get('groups')}"
                assert data.get("message") is not None, "Message should be provided"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]


class TestGroupsPanelBrokenJson:
    """AC-6: Kısmi başarı (dosya var ama bozuk JSON) → 200 + {"groups": [], "cached": false}"""

    def test_groups_endpoint_broken_json_not_500(self):
        """
        Given: groups dosyası bozuk/geçersiz JSON içeriği (parse error)
        When: login'li client /api/whatsapp/groups'a istek attar
        Then: 200 OK + {"groups": [], "cached": false} döner (500 DÖNMEZ)
        """
        valid_token = 'test_broken_json_groups_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                # Write broken JSON
                f.write('{ "groups": [{"id": "123", "name": "incomplete"}')
                temp_groups_path = f.name

            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                # CRITICAL: Should NOT be 500
                assert response.status_code != 500, f"Broken JSON should not cause 500, got {response.status_code}"
                assert response.status_code in [200, 202], f"Should return 200 or 202, got {response.status_code}"

                data = response.get_json()
                # On broken JSON, should return safe response with empty groups and cached=false
                assert data.get("groups") == [], f"Groups should be empty on parse error"
                assert data.get("cached") is False, f"cached should be False on parse error"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)

    def test_groups_endpoint_empty_file(self):
        """
        Given: groups dosyası boş
        When: login'li client /api/whatsapp/groups'a istek attar
        Then: 200/202 + boş dizi döner (500 DÖNMEZ)
        """
        valid_token = 'test_empty_file_groups_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write('')  # Empty file
                temp_groups_path = f.name

            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code != 500, f"Empty file should not cause 500"
                assert response.status_code in [200, 202], f"Should return 200 or 202"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)


class TestGroupsPanelSavedField:
    """AC-2, AC-7: "saved" alanının doğru hesaplanması (data/chat_groups.json ile karşılaştırma)"""

    def test_saved_field_calculation(self):
        """
        Given:
          - groups dosyasında 3 grup: A, B, C
          - chat_groups.json'da A ve C kayıtlı (B değil)
        When: /api/whatsapp/groups çağrılır
        Then: response'daki groups'ta saved: true/false doğru hesaplanmış olur
        """
        valid_token = 'test_saved_field_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        # Bridge.js tarafından yazılacak groups dosyası (Baileys'den gelen)
        groups_content = {
            "groups": [
                {"id": "120363024125432@g.us", "name": "Grup A"},
                {"id": "120363025987654@g.us", "name": "Grup B"},
                {"id": "120363026543210@g.us", "name": "Grup C"},
            ]
        }

        # Chat_groups.json (kayıtlı gruplar) — A ve C kayıtlı, B değil
        registered_groups = [
            {"id": "120363024125432@g.us", "name": "Grup A"},
            {"id": "120363026543210@g.us", "name": "Grup C"},
        ]

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(groups_content, f)
                temp_groups_path = f.name

            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(registered_groups, f)
                temp_registered_path = f.name

            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                with patch.object(admin_panel, 'GROUPS_PATH', temp_registered_path):
                    response = admin_panel.app.test_client().get(
                        '/api/whatsapp/groups',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    assert response.status_code == 200
                    data = response.get_json()
                    groups = data.get("groups", [])

                    # Find groups by ID and check saved field
                    group_a = next((g for g in groups if g["id"] == "120363024125432@g.us"), None)
                    group_b = next((g for g in groups if g["id"] == "120363025987654@g.us"), None)
                    group_c = next((g for g in groups if g["id"] == "120363026543210@g.us"), None)

                    assert group_a is not None, "Group A should be in response"
                    assert group_b is not None, "Group B should be in response"
                    assert group_c is not None, "Group C should be in response"

                    # A ve C kayıtlı (saved=true), B değil (saved=false)
                    assert group_a.get("saved") is True, f"Group A should have saved=true, got {group_a}"
                    assert group_b.get("saved") is False, f"Group B should have saved=false, got {group_b}"
                    assert group_c.get("saved") is True, f"Group C should have saved=true, got {group_c}"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)
            if os.path.exists(temp_registered_path):
                os.unlink(temp_registered_path)


class TestGroupsPanelEdgeCases:
    """Edge case tests"""

    def test_groups_endpoint_with_malformed_bearer_header(self):
        """
        Given: Authorization header'ı "Bearer " ama token boş/eksik
        When: /api/whatsapp/groups'a istek atılır
        Then: 401 döner
        """
        with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', '/tmp/test_groups.json'):
            response = admin_panel.app.test_client().get(
                '/api/whatsapp/groups',
                headers={'Authorization': 'Bearer'}  # Malformed
            )
            assert response.status_code == 401

    def test_groups_endpoint_with_wrong_auth_scheme(self):
        """
        Given: Authorization header'ı "Basic" veya başka scheme'i kullanıyor
        When: /api/whatsapp/groups'a istek atılır
        Then: 401 döner
        """
        with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', '/tmp/test_groups.json'):
            response = admin_panel.app.test_client().get(
                '/api/whatsapp/groups',
                headers={'Authorization': 'Basic dXNlcjpwYXNz'}
            )
            assert response.status_code == 401

    def test_groups_endpoint_empty_groups_array(self):
        """
        Given: groups dosyası boş grup dizisi içeriyor: {"groups": []}
        When: login'li client /api/whatsapp/groups'a istek attar
        Then: 200 + {"groups": [], "cached": true} döner (hiç grup yok ama dosya geçerli)
        """
        valid_token = 'test_empty_groups_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        groups_content = {"groups": []}

        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(groups_content, f)
                temp_groups_path = f.name

            with patch.object(admin_panel, 'BAILEYS_GROUPS_PATH', temp_groups_path):
                response = admin_panel.app.test_client().get(
                    '/api/whatsapp/groups',
                    headers={'Authorization': f'Bearer {valid_token}'}
                )

                assert response.status_code == 200
                data = response.get_json()
                assert data.get("groups") == [], "Should return empty groups array"
                assert data.get("cached") is True, "Should be cached when file is valid"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_groups_path):
                os.unlink(temp_groups_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
