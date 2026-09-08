# Test Diff — webhook-server-threading-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
- `tests/test_webhook_server_threading.py` (yeni, 8 test, Haiku alt-ajanı tarafından yazıldı)

## Gerçek Çalıştırma (orkestratör tarafından doğrulandı)
```
python -m pytest tests/test_webhook_server_threading.py -q
4 failed, 5 passed in 5.76s
```
(İlk yazımda 3 kırmızıydı — orkestratör kapsam boşluğunu tespit edip `vps_main.py`'nin kendi `HTTPServer` kullanımını doğrulayan `test_vps_main_uses_threading_http_server`'ı ekletti, şimdi 4 kırmızı.)

## AC -> Test Mapping
1. AC-1 (eşzamanlılık, ikinci istek <1sn) -> `test_concurrent_requests_with_slow_client` -> RED (bekleniyor, mevcut HTTPServer ~1.03sn timeout ile bloke oluyor)
2. AC-2 (30sn socket timeout) -> `test_handler_has_timeout_attribute` (RED — `timeout` attribute yok), `test_socket_timeout_mechanism` (PASS — mekanizma yapısal olarak zaten stdlib'de var)
3. AC-3 (regresyon, bozuk JSON → 500) -> `test_malformed_json_returns_500` -> PASS (implementasyon öncesi de sonrası da doğru olmalı)
4. AC-4 (thread içinde thread kabul edilebilir, regresyon) -> `test_baileys_event_async_call_in_do_post`, `test_webhook_handler_uses_threading` -> PASS
5. Unit (webhook_server.py'nin ThreadingHTTPServer kullanımı) -> `test_run_server_uses_threading_http_server` -> RED (bekleniyor, hâlâ `HTTPServer`)
6. Unit (vps_main.py'nin ThreadingHTTPServer kullanımı, KRİTİK — üretim giriş noktası) -> `test_vps_main_uses_threading_http_server` -> RED (bekleniyor, ilk yazımda eksikti, orkestratör tespit edip ekletti)
7. Unit (import kontrolü) -> `test_import_threading_http_server` -> PASS (bu test muhtemelen sadece dosyanın importlanabilir olduğunu kontrol ediyor, gerçek ThreadingHTTPServer kullanımını değil — code-copilot sonrası ayrıca doğrulanmalı)

## Şu An Kırmızı (Red) Olan Testler — code-copilot bunları yeşile çevirecek
1. `test_handler_has_timeout_attribute` — `WhapiWebhookHandler.timeout` şu an `None`, `30` olmalı.
2. `test_concurrent_requests_with_slow_client` — mevcut tek-thread'li `HTTPServer` yavaş bir bağlantı varken ikinci isteği bloke ediyor.
3. `test_run_server_uses_threading_http_server` — `webhook_server.py`'nin `run_server()`'ı hâlâ `HTTPServer` kullanıyor.
4. `test_vps_main_uses_threading_http_server` — `vps_main.py`'nin `_start_baileys_webhook_server()`'ı hâlâ `HTTPServer` kullanıyor (PM2'nin canlıda çalıştırdığı asıl dosya).

## Coverage / Quality Notes
- İlk yazımda `vps_main.py`'nin kendi `HTTPServer` instantiation'ını (plan.md'nin kritik bulgusu) doğrulayan bir test YOKTU — orkestratör bu boşluğu tespit edip ek bir dispatch ile `test_vps_main_uses_threading_http_server`'ı ekletti. Artık her iki dosya da (`webhook_server.py` VE `vps_main.py`) yapısal olarak test kapsamında.
- `test_import_threading_http_server`'ın implementasyon öncesi zaten PASS olması şüpheli olabilir (ne test ettiği tam netleşmedi, sub-agent raporunda "Import satırı kontrol" diyor) — `code-copilot` sonrası bu testin gerçekten anlamlı bir şey doğruladığından emin olunmalı, aksi halde zayıf/sahte-yeşil bir test olabilir (önceki görevlerde bu kalıp tekrarlamıştı, `verify`/`red-team` bunu tekrar kontrol etmeli).
