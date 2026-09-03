# Test Diff — baileys-mesaj-guvenilirligi
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
| Dosya | Framework | Çalıştırma |
|---|---|---|
| `sidecar/test_bridge_reliability.js` | Node builtin `assert` | `node sidecar/test_bridge_reliability.js` → **exit code 1** (gerçek — `bridge.js` henüz `getMessage`/`isDecryptFailedMessage` export etmiyor) |
| `tests/test_webhook_baileys_log_level.py` | pytest, `caplog` | `python -m pytest tests/test_webhook_baileys_log_level.py -v` → **4/5 failed** (gerçek — log seviyesi hâlâ `debug`) |
| `tests/test_text_gen_parser_client_close.py` | pytest, `unittest.mock` (AsyncMock) | `python -m pytest tests/test_text_gen_parser_client_close.py -v` → **5/7 failed** (gerçek — `client.close()` hiçbir yerde çağrılmıyor) |

## Bulunan ve Düzeltilen Sorunlar (test dosyalarında, implementasyonda değil)
1. **Yanlış nedenle kırmızı (import hatası):** İlk taslakta her iki Python
   test dosyası da `from google import genai` zincirinden kaynaklanan
   `ImportError` ile patlıyordu — implementasyon eksikliğiyle değil,
   bilinen bir test-ortamı sorunuyla kırmızıydı. `tests/test_dedup_active_ids_fix.py`'deki
   `sys.modules` mock-stub deseni (`google`, `google.genai`, `dotenv`,
   `pymongo`) her iki dosyaya da eklenerek düzeltildi — artık testler
   gerçek AC eksikliğiyle kırmızı.
2. **Gerçek test bug'ı (TypeError):** `test_text_gen_parser_client_close.py`'deki
   `test_no_event_loop_closed_error_with_concurrent_workers`, `thread_worker()`'ı
   parametresiz tanımlayıp `executor.map(thread_worker, range(5))` ile
   argüman geçiyordu → `TypeError`. `thread_worker(idx)` olarak düzeltildi.
3. **Anlamsız testler (mock'un kendi davranışını test eden, implementasyona
   hiç dokunmayan):** `TestClientCloseEdgeCases` sınıfındaki
   `test_client_close_called_multiple_times_is_safe` ve
   `test_close_with_timeout_respected` silindi — ikisi de gerçek
   `parser.parse_async()`'ı hiç çağırmadan sadece `AsyncMock`'un kendi
   davranışını doğruluyordu (CAVEMAN: anlamsız test = gereksiz kod).
   `test_close_exception_does_not_propagate` gerçek `parse_async()` çağrısını
   kullanacak şekilde korunup `TestClientCloseMultiThreaded`'a taşındı.
4. **Docstring artifact'ı:** Haiku'nun ilk taslağında 3 test docstring'i
   yanlışlıkla Korece yazılmıştı (`어떤 이유로든...`) — Türkçeye çevrildi
   (ilgili testler zaten madde 3'te kaldırıldığı/taşındığı için büyük
   ölçüde kendiliğinden çözüldü).

## Bilinen Sınırlama (blocking değil, not düşülüyor)
İki test şu an implementasyon YOKKEN bile PASS ediyor:
- `test_no_event_loop_closed_error_with_concurrent_workers`: `AsyncMock`
  kullandığı için gerçek bir `asyncio`/httpx event-loop çakışması hiç
  oluşmuyor — bu test sadece "mock senaryosunda hata yok" diyor, AC-3'ün
  gerçek kanıtı VPS'te pm2 loglarının gözlemlenmesiyle gelecek (atdd.md'de
  zaten "sayısal hedef yok, gözlemlenmeli" olarak not düşülmüştü).
- `test_close_exception_does_not_propagate`: mevcut kod `close()` hiç
  çağırmadığı için `close()`'un fırlatabileceği hata da hiç oluşmuyor —
  code-copilot `close()` eklediğinde bu test gerçek bir regresyon
  koruması haline gelecek.
Bu iki test SİLİNMEDİ çünkü implementasyon sonrası gerçek bir regresyon
koruması sağlayacaklar — sadece red-step'te "her AC kırmızı olmalı"
kuralına tam uymuyorlar, atdd.md Risks/Unknowns bölümüne uygun şekilde
burada şeffafça not düşüldü.

## AC → Test Eşlemesi
| AC | Davranış | Test Dosyası | Test Fonksiyonu |
|---|---|---|---|
| AC-1 | `getMessage` callback builder + Map-based retrieval | `sidecar/test_bridge_reliability.js` | `testGetMessageFunctionExported`, `testGetMessageReturnsCallable`, `testGetMessageRetrievalLogic`, `testGetMessageUndefinedForMissing` |
| AC-2 | AsyncOpenAI/AsyncGroq client `close()` (başarı + exception) | `tests/test_text_gen_parser_client_close.py` | `test_deepseek_client_closed_on_success`, `test_deepseek_client_closed_on_exception`, `test_groq_client_closed_on_success`, `test_groq_client_closed_on_exception`, `test_all_client_types_closed_in_fallback_chain` |
| AC-3 | Eşzamanlı worker'larda "Event loop is closed" olmamalı | `tests/test_text_gen_parser_client_close.py` | `test_no_event_loop_closed_error_with_concurrent_workers` (bkz. Bilinen Sınırlama) |
| AC-4 | Sessiz düşen mesaj → log seviyesi INFO/WARNING | `tests/test_webhook_baileys_log_level.py` | `test_handle_baileys_event_logs_skipped_unregistered_group_at_info_level`, `test_handle_baileys_event_logs_count_of_skipped_messages`, `test_handle_baileys_event_logs_example_chat_id`, `test_handle_baileys_event_log_level_is_not_debug` |
| AC-5 | Decrypt hatası (`messageStubType === CIPHERTEXT`) tespiti | `sidecar/test_bridge_reliability.js` | `testDecryptCheckFunctionExported`, `testDecryptCheckDetectsCiphertext`, `testDecryptCheckReturnsFalseForNormal` |
| AC-6 | (regresyon) exception → `mark_id_handled`, mevcut davranış korunur | — | Kapsamı `veri_cekici_ayristirici.py`'de değişiklik yapılmadığı için ayrı test yazılmadı, mevcut testler zaten koruyor |
| AC-7 | (regresyon) `MAX_WORKERS_DEFAULT` kod okumasıyla doğrulandı (50) | — | Kod incelemesiyle doğrulandı (plan.md), ayrı test gerektirmiyor |

## code-copilot İçin Bağlayıcı Varsayımlar (test dosyalarından, birebir)
- **`sidecar/bridge.js`**: `module.exports`'a `buildGetMessage(messageHistoryMap)` ve
  `isDecryptFailedMessage(msg)` fonksiyonları eklenmeli. `proto` import'u
  `require('@whiskeysockets/baileys')`'in destructure'ına eklenmeli (plan.md'de
  doğrulandı). `isDecryptFailedMessage`, `msg.messageStubType ===
  proto.WebMessageInfo.StubType.CIPHERTEXT` kontrolü yapmalı.
- **`text_gen_parser.py`**: `parse_async()` içindeki HER `client =
  self._get_deepseek_client()` / `self._get_async_client()` ataması,
  `try/finally` ile (veya `async with`) kullanım sonrası `await
  client.close()` çağırmalı — fallback döngüsündeki (satır 457-590) TÜM
  çıkış yollarında (continue/break/exception) garanti edilmeli.
  `_get_gemini_client()` (satır 95-109) DOKUNULMAYACAK.
- **`src/api/webhook_server.py`**: `_handle_baileys_event()`'teki mevcut
  `logger.debug(...)` (satır ~86) → `logger.info(...)` veya
  `logger.warning(...)`'a çıkarılmalı, mesaj içeriği (atlanan sayı +
  örnek chat_id) korunmalı.
