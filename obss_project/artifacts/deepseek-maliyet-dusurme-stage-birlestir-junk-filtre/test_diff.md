# Test Diff — deepseek-maliyet-dusurme-stage-birlestir-junk-filtre

## Oluşturulan Dosyalar
- `tests/test_stage_merge_call_count.py` (yeni)
- `tests/test_junk_message_filter.py` (yeni)

## AC → Test Eşlemesi
| AC | Test Fonksiyonu | Dosya | Beklenen Durum (implementasyon öncesi) |
|---|---|---|---|
| AC-1 | `test_extract_locations_stage1_not_called` | test_stage_merge_call_count.py | RED (Stage 1 hâlâ ayrı çağrı) |
| AC-1 | `test_api_call_count_single_call_per_message` | test_stage_merge_call_count.py | RED (2 çağrı yapılıyor, 1 bekleniyor) |
| AC-2 | `test_retry_chain_preserved_on_429_error` | test_stage_merge_call_count.py | PASS (regresyon, mevcut davranış zaten doğru) |
| AC-6 | `test_all_models_exhausted_behavior_unchanged` | test_stage_merge_call_count.py | PASS (regresyon) |
| AC-3 | `test_is_junk_message_function_exists` | test_junk_message_filter.py | RED (fonksiyon yok) |
| AC-3 | `test_basic_junk_detection_no_city_no_keywords` | test_junk_message_filter.py | SKIP→RED (fonksiyon yoksa skip, var olunca çalışır) |
| AC-4 | `test_non_junk_with_logistics_keyword_no_city` | test_junk_message_filter.py | SKIP→çalışır |
| AC-4 | `test_non_junk_with_phone_no_city` | test_junk_message_filter.py | SKIP→çalışır |
| AC-4 | `test_mixed_message_with_multiple_signals` | test_junk_message_filter.py | SKIP→çalışır |
| AC-5 | `test_real_shipment_with_city_not_junk` | test_junk_message_filter.py | SKIP→çalışır |
| AC-5 | `test_regression_real_messages_no_false_positives` | test_junk_message_filter.py | SKIP→çalışır (**düzeltme sonrası**: `data/onaylanmamis_ayristirilmis_log.json`'dan 450 gerçek mesaj kullanıyor, ilk dispatch yanlış dosya adı — `_log` eksikti — kullanmıştı, ikinci dispatch'te düzeltildi ve 450 mesajla doğrulandı) |

## Düzeltme Notu
İlk Haiku dispatch'i `test_regression_real_messages_no_false_positives`'te
yanlış dosya adı kullandı (`onaylanmamis_ayristirilmis.json` — bu ortamda
BOŞ, 0 kayıt). İkinci bir Haiku dispatch'iyle `onaylanmamis_ayristirilmis_log.json`
olarak düzeltildi ve 450 gerçek mesaj bulunduğu doğrulandı — test artık
gerçekten çalışacak, sessizce skip olmayacak.

## Sonraki Adım
`code-copilot` — bu testleri geçirecek implementasyonu (Stage birleştirme +
`_is_junk_message()`) yazacak.
