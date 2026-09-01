# Baileys epic #43 - uctan uca test icin GECICI receiver.
# webhook_server.py'nin run_server()'ini COPY ETMEZ - ngrok/setup_webhook
# (Whapi'nin uretim webhook URL'sini degistirebilir) ve periyodik Whapi
# polling dongusu KASITLI OLARAK BASLATILMAZ. Sadece /baileys-webhook
# path'ini gercek orchestrator ile test etmek icindir.
#
# DM testi icin (Saga #350, atdd.md AC-1): TEST_ALLOW_CHAT_ID ortam
# degiskeni set edilirse, sadece o JID'den gelen mesajlar (grup filtresi
# BYPASS edilerek) orchestrator kuyruguna eklenir. UYETIM src/api/
# webhook_server.py'ye HICBIR DEGISIKLIK YAPILMADI - bypass sadece bu
# test-only dosyada yasiyor (atdd.md AC-4).
import sys
import os
import json
import logging

sys.path.insert(0, os.getcwd())

from http.server import HTTPServer
from src.api.webhook_server import WhapiWebhookHandler, orchestrator

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

PORT = 8099  # gercek 8080'den FARKLI - production webhook_server ile catismasin
TEST_ALLOW_CHAT_ID = os.getenv('TEST_ALLOW_CHAT_ID')  # ornek: "905xxxxxxxxx@s.whatsapp.net"


class TestBaileysWebhookHandler(WhapiWebhookHandler):
    """
    TEST ONLY. /baileys-webhook icin, TEST_ALLOW_CHAT_ID ile eslesen
    mesajlari (DM dahil) uretimdeki kayitli-grup filtresini bypass ederek
    dogrudan orchestrator kuyruguna verir. TEST_ALLOW_CHAT_ID set
    edilmezse hicbir mesaj bypass edilmez (bos liste -> hicbir sey olmaz).
    Diger tum path'ler (ve /baileys-webhook disindaki her sey) degismeden
    WhapiWebhookHandler'a devrediliyor.
    """

    def do_POST(self):
        if self.path != '/baileys-webhook':
            return super().do_POST()

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode('utf-8'))

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'received'}).encode('utf-8'))

            messages = data.get('messages', [])
            if not TEST_ALLOW_CHAT_ID:
                logging.warning(
                    "[BAILEYS-TEST] TEST_ALLOW_CHAT_ID set edilmemis - hicbir mesaj bypass edilmiyor "
                    "(bu, uretim davranisiyla ayni: filtrelenmeyen hicbir sey kuyruga girmez)."
                )
                return

            allowed = [m for m in messages if m.get('chat_id') == TEST_ALLOW_CHAT_ID]
            skipped = len(messages) - len(allowed)
            if skipped:
                received_ids = [m.get('chat_id') for m in messages if m.get('chat_id') != TEST_ALLOW_CHAT_ID]
                logging.info(
                    f"[BAILEYS-TEST] {skipped} mesaj TEST_ALLOW_CHAT_ID ile eslesmedi, atlandi. "
                    f"Beklenen: {TEST_ALLOW_CHAT_ID!r} | Gelen chat_id(ler): {received_ids}"
                )

            if allowed:
                logging.info(f"[BAILEYS-TEST] {len(allowed)} mesaj (bypass) kuyruga ekleniyor.")
                orchestrator.add_to_processing_queue(allowed)

        except Exception as e:
            logging.error(f"[BAILEYS-TEST] Hata: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except Exception:
                pass


print(f"[TEST RECEIVER] :{PORT} adresinde dinliyor (SADECE /baileys-webhook test icin, ngrok/Whapi polling YOK)")
if TEST_ALLOW_CHAT_ID:
    print(f"[TEST RECEIVER] TEST_ALLOW_CHAT_ID bypass aktif: {TEST_ALLOW_CHAT_ID}")
else:
    print("[TEST RECEIVER] TEST_ALLOW_CHAT_ID set EDILMEDI - hicbir mesaj bypass edilmeyecek.")
    print("[TEST RECEIVER]   Ornek: TEST_ALLOW_CHAT_ID=\"905xxxxxxxxx@s.whatsapp.net\" python sidecar/test_receiver.py")
print("[TEST RECEIVER] Durdurmak icin Ctrl+C")

server = HTTPServer(('127.0.0.1', PORT), TestBaileysWebhookHandler)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\n[TEST RECEIVER] Durduruldu.")
