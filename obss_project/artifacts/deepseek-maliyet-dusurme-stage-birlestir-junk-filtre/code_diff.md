# Code Diff — deepseek-maliyet-dusurme-stage-birlestir-junk-filtre

## Değiştirilen Dosyalar
- `text_gen_parser.py` — `parse_async()` içindeki Stage 1 çağrısı kaldırıldı;
  eski Stage 1 gövdesi silinip test-uyumluluğu için boş bir stub
  (`return ""`) bırakıldı (testler `patch.object` ile bu metodu mock'luyor,
  metod tamamen silinseydi `AttributeError` verirdi).
- `src/parsers/veri_cekici_ayristirici.py` — modül seviyesinde
  `_is_junk_message()` fonksiyonu eklendi, `add_to_processing_queue()`
  içine (aktif ID/hash setine eklendikten hemen sonra) junk kontrolü
  eklendi.

## Bağımsız Doğrulama (sub-agent iddiasına değil, gerçek koşuma dayalı)
- `git diff` ile her iki dosyanın gerçek değişikliği okundu (sub-agent
  özetine güvenilmedi).
- İlk teslimde şehir listesinde 4 bozuk/kesik giriş bulundu
  (`KIRLLARELII`, `SILVRI`, `KEMALPA`, `MUSTAFAKEMALPA`) — ikinci bir
  Haiku dispatch'iyle düzeltildi (`KIRKLARELI`, `SILIVRI`, `KEMALPASA`,
  `MUSTAFAKEMALPASA`).
- `python -m pytest tests/test_stage_merge_call_count.py
  tests/test_junk_message_filter.py -v` **gerçekten çalıştırıldı**:
  **12/12 PASSED** (9.95s).
- Test dosyalarına dokunulmadığı `git status --short` ile doğrulandı.

## AC Karşılama Durumu
| AC | Durum | Kanıt |
|---|---|---|
| AC-1 | ✅ | `test_extract_locations_stage1_not_called`, `test_api_call_count_single_call_per_message` PASS |
| AC-2 | ✅ | `test_retry_chain_preserved_on_429_error` PASS (regresyon) |
| AC-3 | ✅ | `test_is_junk_message_function_exists`, `test_basic_junk_detection_no_city_no_keywords` PASS |
| AC-4 | ✅ | `test_non_junk_with_logistics_keyword_no_city`, `test_non_junk_with_phone_no_city`, `test_mixed_message_with_multiple_signals` PASS |
| AC-5 | ✅ | `test_regression_real_messages_no_false_positives` PASS — 450 gerçek mesaj üzerinde 0 false-positive |
| AC-6 | ✅ | `test_all_models_exhausted_behavior_unchanged` PASS (regresyon) |

## Kalan Sınırlama (bilinen, kabul edilmiş)
Gerçek maliyet düşüşü DeepSeek bakiyesi yüklenince prod'da (VPS) kullanıcı
tarafından ayrıca doğrulanacak — bu görevin tamamlanma şartı değildi
(atdd.md'de baştan böyle işaretlenmişti).

## Sonraki Adım
`verify` — gerçek test/lint/coverage geçitlerini çalıştıracak.
