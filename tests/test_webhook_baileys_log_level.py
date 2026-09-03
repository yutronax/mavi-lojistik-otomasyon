#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for webhook_server.py _handle_baileys_event log level (baileys-mesaj-guvenilirligi).

Acceptance Criteria (atdd.md):
1. [High] AC-4: Given _handle_baileys_event() bir mesajı kayıtlı grup listesi dışında
   olduğu için atladığında, When bu olur, Then mevcut logger.debug seviyesi
   INFO/WARNING'e çıkarılmalı ve atlanan mesaj sayısı + örnek chat_id log
   satırında görünür olmalı (mevcut satır 84-86 zaten log atıyor ama seviyesi
   debug — üretimde varsayılan log seviyesinde görünmüyor).

Test Technique:
- pytest fixture: caplog (log capturing)
- caplog.set_level(logging.INFO) — INFO seviyesinde ve üstü logları yakala
- patch.object() ile kayıtlı grup dosyasını mock et
- Mesaj gönder, logda INFO/WARNING seviyesinde "atlandı" mesajı doğrula

Key Assumptions (from plan.md):
- webhook_server.py:84-86'daki logger.debug çağrısı logger.info/warning'e çıkarılacak
- Test henüz implementasyon olmadığı için başarısız olacak (red test)
"""

import pytest
import json
import os
import sys
import logging
import tempfile
from unittest.mock import patch, MagicMock, mock_open

# Add project root to path
sys.path.insert(0, os.getcwd())

# Stub out problematic imports BEFORE importing webhook_server
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

from src.api import webhook_server


class TestBaileysLogLevel:
    """AC-4: Log seviyesi üretimde görünür olmalı (DEBUG değil INFO/WARNING)"""

    def test_handle_baileys_event_logs_skipped_unregistered_group_at_info_level(self, caplog):
        """
        Given: _handle_baileys_event() kayıtlı olmayan grup ID'si içeren mesaj alır
        When: fonksiyon çalışır ve grubu filtreleme yapıp atlar
        Then: log seviyesi INFO/WARNING olmalı (DEBUG değil)
             ve log mesajında "atlandı" / "skipped" veya benzeri ifade + chat_id bulunmalı
        """
        # Set caplog to capture at INFO level (higher than DEBUG)
        # DEFAULT üretim seviyesi INFO'dır, yani DEBUG bu seviyelerde görünmez
        caplog.set_level(logging.INFO)

        # Mock kayıtlı grup listesi — sadece grubu 1 var, grup 2 yok
        registered_groups = {
            "120363024125432@g.us": "Kayıtlı Grup 1"
        }

        # Messages: biri kayıtlı (grup 1), ikisi kayıtlı değil (grup 2)
        event_data = {
            "messages": [
                {
                    "id": "msg_1",
                    "body": "Kayıtlı gruptan mesaj",
                    "chat_id": "120363024125432@g.us",  # Kayıtlı
                    "sender_name": "Sender1",
                    "from": "1234567890@s.whatsapp.net",
                    "timestamp": 1694000000
                },
                {
                    "id": "msg_2",
                    "body": "Kayıtlı olmayan grup 1",
                    "chat_id": "120363025987654@g.us",  # Kayıtlı DEĞİL
                    "sender_name": "Sender2",
                    "from": "9876543210@s.whatsapp.net",
                    "timestamp": 1694000001
                },
                {
                    "id": "msg_3",
                    "body": "Kayıtlı olmayan grup 2",
                    "chat_id": "120363026543210@g.us",  # Kayıtlı DEĞİL
                    "sender_name": "Sender3",
                    "from": "1111111111@s.whatsapp.net",
                    "timestamp": 1694000002
                }
            ]
        }

        # Mock CHAT_GROUPS_FILE to return registered groups
        chat_groups_json = json.dumps([{"id": k, "name": v} for k, v in registered_groups.items()])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(chat_groups_json)
            temp_groups_file = f.name

        try:
            # Mock whapi_fetcher.CHAT_GROUPS_FILE path
            with patch('src.fetchers.whapi_fetcher.CHAT_GROUPS_FILE', temp_groups_file):
                # Call _handle_baileys_event with messages where 2 are from unregistered groups
                webhook_server._handle_baileys_event(event_data)

                # Check that there's an info/warning record
                info_records = [r for r in caplog.records if r.levelno >= logging.INFO]

                # At least one record should mention skipped/unregistered groups
                assert len(info_records) > 0, f"Expected INFO/WARNING level log, got: {caplog.text}"

                skipped_mentioned = any(
                    'atlandı' in r.message.lower() or 'skipped' in r.message.lower()
                    for r in info_records
                )
                assert skipped_mentioned, f"Log should mention skipped/atlandı, got: {caplog.text}"

        finally:
            if os.path.exists(temp_groups_file):
                os.unlink(temp_groups_file)

    def test_handle_baileys_event_logs_count_of_skipped_messages(self, caplog):
        """
        Given: 5 mesaj gelse ve 2'si kayıtlı olmayan gruptan gelse
        When: _handle_baileys_event çalışır
        Then: log mesajında "2 mesaj ... atlandı" veya benzeri sayı görünmeli
        """
        caplog.set_level(logging.INFO)

        registered_groups = {
            "120363024125432@g.us": "Grup A",
            "120363025987654@g.us": "Grup B"
        }

        event_data = {
            "messages": [
                {"id": f"msg_{i}", "body": f"Message {i}", "chat_id": f"120363024125432@g.us",
                 "sender_name": f"Sender {i}", "from": f"user{i}@s.whatsapp.net", "timestamp": 1694000000 + i}
                for i in range(3)  # 3 messages from registered group
            ] + [
                {"id": f"msg_unreg_{i}", "body": f"Unregistered {i}", "chat_id": f"120363026543210@g.us",
                 "sender_name": f"UnregSender {i}", "from": f"unreg{i}@s.whatsapp.net", "timestamp": 1694000100 + i}
                for i in range(2)  # 2 messages from unregistered group
            ]
        }

        chat_groups_json = json.dumps([{"id": k, "name": v} for k, v in registered_groups.items()])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(chat_groups_json)
            temp_groups_file = f.name

        try:
            with patch('src.fetchers.whapi_fetcher.CHAT_GROUPS_FILE', temp_groups_file):
                webhook_server._handle_baileys_event(event_data)

                # Check caplog for mention of the number 2 (skipped count)
                info_records = [r for r in caplog.records if r.levelno >= logging.INFO]

                # At least one record should mention skipped count
                found_count = any(
                    '2' in r.message and ('atlandı' in r.message.lower() or 'skipped' in r.message.lower())
                    for r in info_records
                )
                assert found_count, f"Log should mention '2 mesaj atlandı', got: {caplog.text}"

        finally:
            if os.path.exists(temp_groups_file):
                os.unlink(temp_groups_file)

    def test_handle_baileys_event_logs_example_chat_id(self, caplog):
        """
        Given: kayıtlı olmayan gruplardan mesaj atlanırken
        When: log yazılır
        Then: örnek bir chat_id (atlanmış grup ID'si) log mesajında görünmeli
        """
        caplog.set_level(logging.INFO)

        registered_groups = {
            "120363024125432@g.us": "Grup A"
        }

        unregistered_chat_id = "999999999999999@g.us"

        event_data = {
            "messages": [
                {
                    "id": "msg_1",
                    "body": "Message from unregistered",
                    "chat_id": unregistered_chat_id,
                    "sender_name": "Sender",
                    "from": "user@s.whatsapp.net",
                    "timestamp": 1694000000
                }
            ]
        }

        chat_groups_json = json.dumps([{"id": k, "name": v} for k, v in registered_groups.items()])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(chat_groups_json)
            temp_groups_file = f.name

        try:
            with patch('src.fetchers.whapi_fetcher.CHAT_GROUPS_FILE', temp_groups_file):
                webhook_server._handle_baileys_event(event_data)

                info_records = [r for r in caplog.records if r.levelno >= logging.INFO]

                # At least one record should mention the unregistered chat_id
                found_chat_id = any(
                    unregistered_chat_id in r.message
                    for r in info_records
                )
                assert found_chat_id, f"Log should mention chat_id {unregistered_chat_id}, got: {caplog.text}"

        finally:
            if os.path.exists(temp_groups_file):
                os.unlink(temp_groups_file)

    def test_handle_baileys_event_log_level_is_not_debug(self, caplog):
        """
        Critical: Log seviyesi DEBUG olmamalı, production default seviyesinde (INFO) görünmeli

        Given: caplog.set_level(logging.DEBUG) yapılsa bile
        When: _handle_baileys_event çalışır ve mesaj atlar
        Then: log kaydı INFO/WARNING seviyesinde olmalı (code: DEBUG değil)
        """
        caplog.set_level(logging.DEBUG)

        registered_groups = {
            "120363024125432@g.us": "Grup A"
        }

        event_data = {
            "messages": [
                {
                    "id": "msg_1",
                    "body": "Unregistered",
                    "chat_id": "999999999999999@g.us",
                    "sender_name": "Sender",
                    "from": "user@s.whatsapp.net",
                    "timestamp": 1694000000
                }
            ]
        }

        chat_groups_json = json.dumps([{"id": k, "name": v} for k, v in registered_groups.items()])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(chat_groups_json)
            temp_groups_file = f.name

        try:
            with patch('src.fetchers.whapi_fetcher.CHAT_GROUPS_FILE', temp_groups_file):
                webhook_server._handle_baileys_event(event_data)

                # Find the record about skipped messages
                skipped_records = [
                    r for r in caplog.records
                    if ('atlandı' in r.message.lower() or 'skipped' in r.message.lower())
                ]

                # At least one should exist
                assert len(skipped_records) > 0, f"Expected skipped message log, got: {caplog.text}"

                # CRITICAL: log level should be INFO or WARNING, not DEBUG
                for record in skipped_records:
                    assert record.levelno >= logging.INFO, \
                        f"Log level should be INFO ({logging.INFO}) or higher, got {record.levelno} (DEBUG={logging.DEBUG})"

        finally:
            if os.path.exists(temp_groups_file):
                os.unlink(temp_groups_file)

    def test_handle_baileys_event_all_messages_registered(self, caplog):
        """
        Given: tüm mesajlar kayıtlı gruplardan geliyorsa
        When: _handle_baileys_event çalışır
        Then: "atlandı" veya skip mesajı OLMAMALI (tüm mesajlar işleniyor)
        """
        caplog.set_level(logging.INFO)

        registered_groups = {
            "120363024125432@g.us": "Grup A",
            "120363025987654@g.us": "Grup B"
        }

        event_data = {
            "messages": [
                {"id": "msg_1", "body": "Message 1", "chat_id": "120363024125432@g.us",
                 "sender_name": "Sender 1", "from": "user1@s.whatsapp.net", "timestamp": 1694000000},
                {"id": "msg_2", "body": "Message 2", "chat_id": "120363025987654@g.us",
                 "sender_name": "Sender 2", "from": "user2@s.whatsapp.net", "timestamp": 1694000001}
            ]
        }

        chat_groups_json = json.dumps([{"id": k, "name": v} for k, v in registered_groups.items()])

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(chat_groups_json)
            temp_groups_file = f.name

        try:
            with patch('src.fetchers.whapi_fetcher.CHAT_GROUPS_FILE', temp_groups_file):
                webhook_server._handle_baileys_event(event_data)

                # No skip/atlandı messages should appear
                skip_records = [
                    r for r in caplog.records
                    if 'atlandı' in r.message.lower() or 'skipped' in r.message.lower()
                ]

                assert len(skip_records) == 0, f"No skip messages should appear when all groups registered, got: {caplog.text}"

        finally:
            if os.path.exists(temp_groups_file):
                os.unlink(temp_groups_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
