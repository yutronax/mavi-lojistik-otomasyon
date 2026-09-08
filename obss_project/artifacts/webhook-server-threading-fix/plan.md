# Plan — webhook-server-threading-fix
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/webhook_server.py | (1) `run_server()` (satır ~272) `HTTPServer` yerine `ThreadingHTTPServer` kullanmalı. (2) `WhapiWebhookHandler` sınıfına `timeout = 30` class attribute'u eklenmeli — `http.server.BaseHTTPRequestHandler`, `socketserver.StreamRequestHandler`'dan türediği için bu attribute stdlib tarafından otomatik olarak `self.connection.settimeout(30)` çağrısına dönüştürülür (`StreamRequestHandler.setup()`), ekstra kod gerekmez. | low |
| vps_main.py | **KRİTİK — atdd.md'nin "Unknowns" sorusu burada çözüldü.** `_start_baileys_webhook_server()` (satır 56-87) KENDİ AYRI `HTTPServer` örneğini oluşturuyor (satır 83, `server = HTTPServer(('0.0.0.0', port), handler_class)`) — `webhook_server.py`'nin `run_server()`'ını KULLANMIYOR (yorumda bilinçli olarak belirtilmiş, satır 66-72: iki ayrı orchestrator instance'ının aynı JSON dosyalarına yazması riskini önlemek için). PM2'nin `mavi-lojistik-server` process'i (canlıda tıkanan servis) BU dosyayı çalıştırıyor — yani asıl düzeltme burada olmalı: `from http.server import HTTPServer` yerine `from http.server import ThreadingHTTPServer` import edilip satır 83'te kullanılmalı. `timeout=30` ayrı bir kod gerekmiyor çünkü `WhapiWebhookHandler` sınıfının kendisinde (yukarıdaki satırda) tanımlanacak, `vps_main.py` sadece o sınıfı `make_webhook_handler_class()` ile kullanıyor. | medium |

Bu görev rendered bir web UI dosyasına dokunmuyor — `verify` adımında gate 7/12 N/A kalmalı.

## New Files
| File | Purpose |
|------|---------|
| tests/test_webhook_server_threading.py | AC-1..AC-4'ü kapsayan entegrasyon testleri: gerçek `ThreadingHTTPServer` başlatıp gerçek soket üzerinden bir bağlantıyı kasıtlı geciktirirken ikinci bağlantının hızlı yanıtlandığını, 30sn timeout'un gerçekten tetiklendiğini, mevcut hata davranışının (bozuk JSON → 500) değişmediğini doğrular. |

## Dependencies
- `http.server.ThreadingHTTPServer` — Python 3.7+ stdlib'de zaten mevcut, ek bağımlılık yok.
- `socketserver.StreamRequestHandler.timeout` mekanizması — `BaseHTTPRequestHandler`'ın miras aldığı, stdlib'in kendi timeout deseni (harici kütüphane gerekmez).
- `make_webhook_handler_class()` (`webhook_server.py`, satır 166-175) — `vps_main.py`'nin kullandığı fabrika fonksiyonu, imzası DEĞİŞMEYECEK (sadece döndürdüğü sınıfın `timeout` attribute'u eklenecek).
- `webhook_server.py`'nin kendi `run_server()`'ı — masaüstü GUI kullanımı için hâlâ var, atdd.md'nin Kapsam Dışı kararına göre genel mimarisi (ngrok, kendi orchestrator singleton'ı) değişmeyecek, sadece `HTTPServer`→`ThreadingHTTPServer` satırı.

## Migration Required?
Hayır — kod/altyapı değişikliği, veri şeması yok.

## Risks
- (atdd.md'den taşındı) Sadece `ThreadingHTTPServer`'a geçmek tek başına yeterli değil — `timeout` class attribute'u da mutlaka eklenmeli, aksi halde sınırsız sayıda yavaş bağlantı sınırsız thread açıp kaynak tüketebilir (yavaş DoS riski). Plan bu ikisini AYNI değişiklikte, `WhapiWebhookHandler` sınıfında birlikte ele alıyor.
- `vps_main.py`'nin `_start_baileys_webhook_server()`'ının docstring'i (satır 58-72) iki ayrı orchestrator instance'ının aynı JSON dosyalarına eşzamanlı yazma riskini zaten belgelemiş — `ThreadingHTTPServer`'a geçiş bu riski ARTIRMAZ, çünkü ağır iş zaten `_handle_baileys_event`'in kendi ayrı thread'inde yapılıyor (atdd.md AC-4, "thread içinde thread" kabul edilebilir bulundu); ancak `code-copilot` bu docstring'i güncellemeli mi (ThreadingHTTPServer'a geçildiğini not düşmek için) diye bir küçük belgeleme notu eklenebilir — zorunlu değil, CAVEMAN: sadece gerçek davranış değişikliği belgelenir.
- Test dosyasının gerçek soket açıp kapatması (entegrasyon testi) CI ortamında port çakışması riski taşıyabilir — rastgele/geçici port (`port=0`) kullanılarak azaltılmalı.

## Open Questions
Yok — atdd.md'nin tek "Unknown"ı (vps_main.py'nin webhook_server.py'yi çağırma şekli) yukarıdaki kod keşfiyle tamamen çözüldü, alt-ajana gerek kalmadı.
