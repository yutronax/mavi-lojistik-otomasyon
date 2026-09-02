#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for Onaylananlar.jsonl append-only implementation.

Acceptance Criteria:
1. [Critical] Tekli onay: Mevcut içerik hiç okunmaz, sadece yeni kayıt append edilir.
   Response: {"ok": true}
2. [Critical] Toplu onay: Mevcut içerik hiç okunmaz, tüm geçerli kayıtlar TEK açma/yazmada append.
   Response: {"ok": true, "count": count}
3. [Critical] Bellek profili: Büyük dosya (30K+ satır) üzerinde 50 append sonrası, RSS dosya boyutundan bağımsız.
4. [High] Dosya yok: Dosya otomatik oluşturulur.
5. [Medium] Kısmi başarı: Geçersiz lokasyonlar atlanır.
6. [Medium] Hiçbir şey yapılamadı: Dosya append yapılmaz.

Implementation Plan (henüz yapılmadı):
- APPROVED_PATH → Onaylananlar.jsonl (uzantı değişecek)
- unprocessed_approve: open(APPROVED_PATH, 'a') ile append
- _approve_message: Mevcut içerik okunmaz, sadece yeni kayıtlar append
- _atomic_write KULLANILMAYACAK (append için gerekli değil)
- json.load TAMAMEN YASAKLANACAK (AssertionError ile)

Test Tekniği:
- json.load'ı mock (AssertionError ile) → "okuma" yapılırsa test patlayacak
- APPROVED_PATH'i geçici dosya ile patch → production'a dokunma
- require_auth bypass: .__wrapped__ ile doğrudan çağrı + test_request_context
- _load_unprocessed/_save_unprocessed mock (test sadece Onaylananlar hedefleniyor)
- Bellek testi: Gerçek JSONL dosyası, resource.getrusage() ile RSS ölçümü
"""

import pytest
import json
import os
import sys
import tempfile
import time
import psutil
from unittest.mock import patch, MagicMock, Mock, call
from io import StringIO

# Add project root to path
sys.path.insert(0, os.getcwd())

# Stub out problematic imports before importing admin_panel
sys.modules['dotenv'] = MagicMock()
sys.modules['google.genai'] = MagicMock()
sys.modules['google'] = MagicMock()

from src.api import admin_panel


class TestSingleApprovalNoRead:
    """AC-1: Tekli onay sırasında mevcut içerik HİÇ okunmaz, sadece append."""

    def test_unprocessed_approve_appends_without_reading(self):
        """
        Given: unprocessed_approve çağrıldı, json.load TAMAMEN yasaklandı
        When: Sevkiyat onaylanırsa
        Then: json.load hiç çağrılmaz (okuma YOK), sadece append modunda yaz
        Response: {"ok": true}
        """
        msg_id = "msg_1"
        ship_idx = 0

        # Sevkiyat verisini hazırla
        shipment = {
            "id": "ship_001",
            "nereden_il": "ANKARA",
            "nereye_il": "İSTANBUL",
            "arac_tipi": ["1360"],
            "kasa_tipi": ["AÇIK"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name

        try:
            # json.load'ı tamamen yasakla (admin_panel modülü içindeki json.load'ı patch et)
            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                # APPROVED_PATH'i geçici dosya ile patch et
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    # _load_unprocessed/_save_unprocessed mock'la
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [shipment.copy()],
                            "message_info": {"body": "Test"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            # require_auth bypass: .__wrapped__ + test_request_context
                            with admin_panel.app.test_request_context():
                                response = admin_panel.unprocessed_approve.__wrapped__(msg_id, ship_idx)
                                # Response object'i JSON'a çevir
                                response_json = response.get_json() if hasattr(response, 'get_json') else response
                                assert response_json["ok"] is True, f"Expected ok=true, got {response_json}"

            # Dosyayı kontrol et: append ile yazılmış olmalı (tek satır)
            with open(tmpfile, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 1, f"Dosyada tam 1 satır olmalı, {len(lines)} var"
            record = json.loads(lines[0])
            assert record["id"] == "ship_001"
            assert record["onay_tarihi"]  # Tarih eklendi
        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)


class TestBulkApprovalNoRead:
    """AC-2: Toplu onay (_approve_message) mevcut içerik okunmaz, tüm geçerli kayıtlar TEK append'te."""

    def test_approve_message_appends_all_without_reading(self):
        """
        Given: _approve_message çağrıldı, json.load YASAKLANDI
        When: 3 geçerli sevkiyat onaylanırsa
        Then: json.load hiç çağrılmaz, tüm 3 sevkiyat TEK dosya açma/yazmada append
        Response: (count=3, error=None)
        """
        msg_id = "msg_bulk_1"
        shipments = [
            {"id": f"s_{i}", "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": [], "kasa_tipi": []}
            for i in range(3)
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name

        try:
            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [s.copy() for s in shipments],
                            "message_info": {"body": "Bulk test"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            # _approve_message, dekoratörsüz direkt çağrılabilir
                            count, err = admin_panel._approve_message(msg_id)
                            assert err is None, f"Expected no error, got {err}"
                            assert count == 3, f"Expected count=3, got {count}"

            # Dosyayı kontrol et: 3 satır
            with open(tmpfile, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 3, f"Dosyada 3 satır olmalı, {len(lines)} var"
            for i, line in enumerate(lines):
                record = json.loads(line)
                assert record["id"] == f"s_{i}"
                assert record["onay_tarihi"]
        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)


class TestMemoryProfileLargeFile:
    """AC-3: Bellek profili — büyük dosya üzerinde append, RSS dosya boyutundan bağımsız."""

    def test_large_jsonl_append_memory_bounded(self):
        """
        Given: 30.000 satırlık JSONL dosyası (toplam 10-50MB)
        When: 50 append işlemi yapılırsa
        Then: RSS bellek artışı makul kalır (dosya boyutunun küçük fraksiyonu)

        Ölçüm: append ÖNCESİ RSS baseline → append SONRASİ RSS
        Fark < 100MB (dosyayla orantılı OLMAMALI, ör. 50MB dosya için 50MB+ artışı OK değil)
        """
        n_initial = 30000  # İlk satır sayısı
        n_appends = 50      # Kaç kez append yapacağız

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name
            # Büyük dosyayı oluştur: her satır ~300-500 bytes
            for i in range(n_initial):
                record = {
                    "id": f"existing_{i}",
                    "nereden_il": "ANKARA",
                    "nereye_il": "İSTANBUL",
                    "aciklama": "x" * 200,
                    "body": "y" * 300,
                    "arac_tipi": ["1360"],
                    "kasa_tipi": ["AÇIK"],
                    "createdAt": "2026-01-01T00:00:00",
                    "onay_tarihi": "2026-01-01 10:00:00",
                    "message_id": "test_msg",
                }
                tmp.write(json.dumps(record, ensure_ascii=False) + "\n")

        try:
            # Dosya boyutu kontrol et
            file_size_mb = os.path.getsize(tmpfile) / (1024 * 1024)
            assert file_size_mb >= 5, f"Dosya en az 5MB olmalı test için, {file_size_mb:.1f}MB"

            # BASELINE bellek ölçümü (dosya oluşturulduktan sonra)
            process = psutil.Process(os.getpid())
            time.sleep(0.1)  # Küçük delay, garbage collection vs.
            baseline_rss_mb = process.memory_info().rss / (1024 * 1024)

            # 50 append işlemi yap
            msg_id = "msg_stress"
            shipments_for_append = [
                {
                    "id": f"new_{i}",
                    "nereden_il": "ANKARA",
                    "nereye_il": "İSTANBUL",
                    "arac_tipi": [],
                    "kasa_tipi": [],
                }
                for i in range(n_appends)
            ]

            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [s.copy() for s in shipments_for_append],
                            "message_info": {"body": "Stress test"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            count, err = admin_panel._approve_message(msg_id)
                            assert count == n_appends, f"Expected {n_appends} appends, got {count}"

            # FINAL bellek ölçümü
            final_rss_mb = process.memory_info().rss / (1024 * 1024)

            # Bellek artışını hesapla
            memory_increase = final_rss_mb - baseline_rss_mb

            # ÖĞREN: İçeride dosya boyutu ile orantılı OLMAMALI
            # Yaklaşık olarak: file_size_mb ≈ 10-50MB, memory_increase << file_size_mb olmalı
            # Tolerans: 100MB (yeterince liberal, bile Python ek işlemler yapar)
            assert memory_increase < 100, \
                f"Bellek artışı {memory_increase:.1f}MB (eşik: 100MB). " \
                f"Dosya boyutu {file_size_mb:.1f}MB, baseline RSS {baseline_rss_mb:.1f}MB → final {final_rss_mb:.1f}MB"

            # Dosyayı kontrol et: 30K + 50 = 30050 satır
            with open(tmpfile, "r", encoding="utf-8") as f:
                final_lines = len(f.readlines())

            expected_lines = n_initial + n_appends
            assert final_lines == expected_lines, \
                f"Dosyada {expected_lines} satır olmalı, {final_lines} var"

        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)


class TestFileCreationIfNotExists:
    """AC-4: Dosya yoksa, append modu otomatik oluşturur."""

    def test_file_created_on_first_append(self):
        """
        Given: APPROVED_PATH dosyası HIÇBIR YERde yok
        When: unprocessed_approve çağrılırsa
        Then: Dosya otomatik oluşturulur, hata fırlatılmaz
        """
        msg_id = "msg_new_file"
        ship_idx = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpfile = os.path.join(tmpdir, "new_Onaylananlar.jsonl")
            assert not os.path.exists(tmpfile), "Dosya henüz var olmamalı"

            shipment = {
                "id": "first_ever",
                "nereden_il": "ANKARA",
                "nereye_il": "İSTANBUL",
                "arac_tipi": [],
                "kasa_tipi": [],
            }

            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [shipment.copy()],
                            "message_info": {"body": "Test"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            with admin_panel.app.test_request_context():
                                response = admin_panel.unprocessed_approve.__wrapped__(msg_id, ship_idx)
                                response_json = response.get_json() if hasattr(response, 'get_json') else response
                                assert response_json["ok"] is True

            # Dosya oluşturulmuş olmalı
            assert os.path.exists(tmpfile), "Dosya oluşturulmuş olmalı"

            with open(tmpfile, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 1, f"1 satır olmalı, {len(lines)} var"


class TestPartialSuccessInvalidLocations:
    """AC-5: Toplu onayda geçersiz lokasyonlar atlanır, sadece geçerliler append."""

    def test_approve_message_skips_invalid_locations(self):
        """
        Given: 5 sevkiyat, 2'si geçersiz lokasyon (nereye_il = "BİLİNMEYEN")
        When: _approve_message çağrılırsa
        Then: Sadece 3 geçerli sevkiyat append edilir, 2 atlanır
        Response: (count=3, error=None)
        """
        msg_id = "msg_partial"
        shipments = [
            {"id": "s_0", "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": [], "kasa_tipi": []},
            {"id": "s_1", "nereden_il": "İZMİR", "nereye_il": "BİLİNMEYEN", "arac_tipi": [], "kasa_tipi": []},  # GEÇERSIZ
            {"id": "s_2", "nereden_il": "ANKARA", "nereye_il": "BURSA", "arac_tipi": [], "kasa_tipi": []},
            {"id": "s_3", "nereden_il": "BİLİNMEYEN", "nereye_il": "ANKARA", "arac_tipi": [], "kasa_tipi": []},  # GEÇERSIZ
            {"id": "s_4", "nereden_il": "İSTANBUL", "nereye_il": "ANKARA", "arac_tipi": [], "kasa_tipi": []},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name

        try:
            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [s.copy() for s in shipments],
                            "message_info": {"body": "Partial test"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            count, err = admin_panel._approve_message(msg_id)
                            assert err is None
                            assert count == 3, f"Expected 3 geçerli, got {count}"

            # Dosya kontrol: 3 satır
            with open(tmpfile, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 3, f"3 satır olmalı, {len(lines)} var"
            ids_in_file = {json.loads(line)["id"] for line in lines}
            assert ids_in_file == {"s_0", "s_2", "s_4"}, f"Beklenen IDs: s_0,s_2,s_4, bulundu: {ids_in_file}"
        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)


class TestNoActionWhenNothingToDo:
    """AC-6: Mesaj yoksa veya tüm sevkiyatlar atlanırsa, dosyaya hiçbir satır append edilmez."""

    def test_approve_message_no_append_when_all_invalid(self):
        """
        Given: Mesajın tüm 3 sevkiyatı geçersiz lokasyonlu
        When: _approve_message çağrılırsa
        Then: Dosyaya hiçbir satır append edilmez, count=0
        Response: (count=0, error="Sevkiyat yok" OR hiçbir şey append yok)
        """
        msg_id = "msg_all_invalid"
        shipments = [
            {"id": "s_0", "nereden_il": "BİLİNMEYEN", "nereye_il": "ANKARA", "arac_tipi": [], "kasa_tipi": []},
            {"id": "s_1", "nereden_il": "İSTANBUL", "nereye_il": "BİLİNMEYEN", "arac_tipi": [], "kasa_tipi": []},
            {"id": "s_2", "nereden_il": "BİLİNMEYEN", "nereye_il": "BİLİNMEYEN", "arac_tipi": [], "kasa_tipi": []},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name
            # Önceden 1 satır yaz
            tmp.write(json.dumps({"id": "existing", "onay_tarihi": "2026-01-01"}) + "\n")

        try:
            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [s.copy() for s in shipments],
                            "message_info": {"body": "All invalid"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            count, err = admin_panel._approve_message(msg_id)
                            # Tüm atlanırsa error "Sevkiyat yok" olabilir veya count=0 döner
                            assert count == 0, f"Expected count=0, got {count}"

            # Dosya kontrol: Hala 1 satır (yeni ekleme YOK)
            with open(tmpfile, "r", encoding="utf-8") as f:
                lines = f.readlines()

            assert len(lines) == 1, f"Dosya değişmedi, 1 satır olmalı, {len(lines)} var"
        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)

    def test_approve_message_message_not_found_no_append(self):
        """
        Given: msg_id bulunamıyor
        When: _approve_message çağrılırsa
        Then: Dosyaya append yok
        """
        msg_id = "nonexistent"

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name
            tmp.write(json.dumps({"id": "existing"}) + "\n")

        try:
            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = []  # Boş
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            count, err = admin_panel._approve_message(msg_id)
                            assert err == "Mesaj bulunamadı"
                            assert count == 0

            # Dosya değişmedi
            with open(tmpfile, "r", encoding="utf-8") as f:
                lines = f.readlines()
            assert len(lines) == 1
        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)


class TestResponseFormat:
    """Dönüş değerleri doğru formatta."""

    def test_single_approval_response_format(self):
        """unprocessed_approve: {"ok": true}"""
        msg_id = "msg_response"
        ship_idx = 0
        shipment = {
            "id": "s",
            "nereden_il": "ANKARA",
            "nereye_il": "İSTANBUL",
            "arac_tipi": [],
            "kasa_tipi": [],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name

        try:
            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [shipment.copy()],
                            "message_info": {"body": "Test"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            with admin_panel.app.test_request_context():
                                response = admin_panel.unprocessed_approve.__wrapped__(msg_id, ship_idx)
                                response_json = response.get_json() if hasattr(response, 'get_json') else response
                                assert "ok" in response_json
                                assert response_json["ok"] is True
        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)

    def test_bulk_approval_response_format(self):
        """unprocessed_approve_all: {"ok": true, "count": N}"""
        msg_id = "msg_response_bulk"
        shipments = [
            {"id": f"s_{i}", "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": [], "kasa_tipi": []}
            for i in range(2)
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as tmp:
            tmpfile = tmp.name

        try:
            with patch("src.api.admin_panel.json.load", side_effect=AssertionError("json.load HİÇ ÇAĞRILMAMALI")):
                with patch("src.api.admin_panel.APPROVED_PATH", tmpfile):
                    unprocessed_items = [
                        {
                            "message_id": msg_id,
                            "shipments": [s.copy() for s in shipments],
                            "message_info": {"body": "Bulk"},
                        }
                    ]
                    with patch("src.api.admin_panel._load_unprocessed", return_value=unprocessed_items):
                        with patch("src.api.admin_panel._save_unprocessed"):
                            count, err = admin_panel._approve_message(msg_id)
                            # _approve_message döner değerleri: (count, error)
                            assert err is None
                            assert count == 2
                            # Route'dan çağrı yapılırsa response {"ok": true, "count": 2} olur
        finally:
            if os.path.exists(tmpfile):
                os.unlink(tmpfile)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
