# Plan — baileys-webhook-bridge-uctan-uca-test
_Reference: atdd.md_

## Kararlı: bypass nerede yaşayacak
ATDD'nin Unknowns bölümünde bıraktığı karar burada netleşiyor: **üretim
`src/api/webhook_server.py`'ye hiçbir değişiklik yapılmayacak.**
`sidecar/test_receiver.py` zaten `WhapiWebhookHandler`'ı wholesale import
edip kullanıyordu — bunun yerine sadece `/baileys-webhook` path'i için
davranışı override eden **kendi alt sınıfını** tanımlayacak. Bu, AC-4'ü
(üretim davranışı hiç değişmeden kalmalı) en güçlü şekilde sağlar —
`webhook_server.py`'de "eğer env var set edilmediyse" diye bir dallanma
bile olmayacak, çünkü o dosyaya hiç dokunulmuyor.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `sidecar/test_receiver.py` | `TestBaileysWebhookHandler` alt sınıfı eklenecek: `/baileys-webhook` POST'unu `TEST_ALLOW_CHAT_ID` ortam değişkenindeki JID'e göre filtreleyip doğrudan `orchestrator.add_to_processing_queue()`'ya versin (üretim `_handle_baileys_event`'in grup-filtresini bypass eder, ama sadece bu test dosyasında) | low — üretim dosyasına dokunulmuyor, sadece test-only dosya genişliyor |

## New Files
Yok.

## Dependencies
- `src.api.webhook_server.orchestrator` (var olan singleton, doğrudan import edilip kullanılacak — `add_to_processing_queue` zaten public metod)
- `src.fetchers.whapi_fetcher.CHAT_GROUPS_FILE` gerekmez (bu handler grup filtresi uygulamıyor, sadece `TEST_ALLOW_CHAT_ID` eşleşmesi kontrol ediyor)

## Migration Required?
Hayır — şema/veri değişikliği yok, geçici bir test kaydı `data/mesajlar.json`'a yazılıp test sonunda temizlenecek (kod değil, veri).

## Uygulama Detayı (code-copilot'a devredilecek özet)
`test_receiver.py`'ye eklenecek mantık:

```python
class TestBaileysWebhookHandler(WhapiWebhookHandler):
    def do_POST(self):
        if self.path == '/baileys-webhook':
            allow_jid = os.getenv('TEST_ALLOW_CHAT_ID')
            content_length = int(self.headers['Content-Length'])
            data = json.loads(self.rfile.read(content_length))
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'status': 'received'}).encode())

            messages = data.get('messages', [])
            if allow_jid:
                messages = [m for m in messages if m.get('chat_id') == allow_jid]
            if messages:
                logging.info(f"[BAILEYS-TEST] {len(messages)} mesaj (TEST_ALLOW_CHAT_ID bypass) kuyruğa ekleniyor.")
                orchestrator.add_to_processing_queue(messages)
        else:
            super().do_POST()
```

`server = HTTPServer(('127.0.0.1', PORT), TestBaileysWebhookHandler)` olarak değiştirilecek.
`orchestrator`, `json`, `logging` import'ları `webhook_server`'dan/standart kütüphaneden eklenecek.

Kullanım:
```bash
TEST_ALLOW_CHAT_ID="<kullanıcının DM JID'i>@s.whatsapp.net" python sidecar/test_receiver.py
```

## Test/Doğrulama Sırası (kullanıcı için, code-copilot sonrası)
1. `TEST_ALLOW_CHAT_ID=<DM JID> python sidecar/test_receiver.py` başlat, `[TEST RECEIVER]` log'unu bekle.
2. Ayrı terminalde `WEBHOOK_URL=http://127.0.0.1:8099/baileys-webhook node sidecar/bridge.js` başlat, `[BAGLANDI]` log'unu bekle.
3. **Ancak ikisi de ayaktayken** kullanıcı test WhatsApp numarasına kendi telefonundan bir DM gönderir (içinde ayırt edici bir kelime/UUID ile).
4. `bridge.js` konsolunda `[WEBHOOK OK]`, `test_receiver.py` konsolunda `[BAILEYS-TEST] 1 mesaj ... kuyruğa ekleniyor` aranır.
5. `data/mesajlar.json`'da test mesajı UUID'siyle bulunur.
6. Temizlik: test mesajının `id`'si `data/mesajlar.json` ve `data/islenmemis_mesajlar.json`'dan script ile silinir (küçük bir temizlik script'i code-copilot'ta yazılacak).

## Risks
- ATDD'deki risk aynen geçerli: kullanıcı mesajı dinleyiciler ayakta olmadan gönderirse mesaj sessizce kaybolur (WhatsApp'ta kalır, sisteme hiç girmez) — bu yüzden 3. adımdan önce 1-2 adımların tamamlanması kullanıcıya açıkça hatırlatılacak.
- Kullanıcının gerçek DM JID'i bilinmiyor (`<numara>@s.whatsapp.net` formatında) — code-copilot bunu placeholder bırakacak, kullanıcı kendi numarasıyla dolduracak (ya da `bridge_unhandled_messages.log`/`poc_messages.log`'daki geçmiş kayıtlardan tahmin edilebilir, ama en güvenlisi kullanıcının kendi numarasını vermesi).

## Open Questions
Yok — ATDD'deki tek açık soru (bypass'ın nerede yaşayacağı) bu planda netleşti.
