# Code Diff — saatlik-harcama-ust-limit

## Değiştirilen Dosyalar
- `text_gen_parser.py` — modül seviyesinde `_hourly_lock`, `_current_hour_key`,
  `_current_hour_cost_try`, `_get_current_hour_key()`, `_init_hourly_counter_
  from_file()`, `is_hourly_cap_exceeded()` eklendi; `_track_spend()`'in içine
  saat penceresi güncelleme kodu eklendi; modül yüklenirken restart-kurtarma
  için `_init_hourly_counter_from_file()` bir kez çağrılıyor.
- `src/parsers/veri_cekici_ayristirici.py` — `import text_gen_parser` eklendi,
  `add_to_processing_queue()`'da junk-filtre kontrolünden hemen sonra,
  `processing_queue.put()`'tan önce saatlik limit kontrolü eklendi (limit
  aşılırsa mesaj kuyruğa eklenmiyor, `mark_id_handled` çağrılmıyor — mevcut
  "aktif/duplicate skip" örüntüsü taklit edildi, ayrı bir erteleme yapısı
  icat edilmedi).

## Bağımsız Doğrulama
- `git diff` ile her iki dosyanın gerçek değişikliği okundu.
- `python -m pytest tests/test_hourly_spend_cap.py -v` **gerçekten
  çalıştırıldı**: **10/10 PASSED (1.50s)**.
- Test dosyasına dokunulmadığı doğrulandı.

## AC Karşılama Durumu
| AC | Durum | Kanıt |
|---|---|---|
| AC-1 | ✅ | `test_ac1_threshold_below_cap_returns_false`, `test_ac1_integration_add_to_processing_queue_allows_under_cap` PASS |
| AC-2 | ✅ | `test_ac2_exceeds_cap_returns_true`, `test_ac2_custom_cap_env_variable`, `test_ac2_ac3_integration_...` PASS |
| AC-3 | ✅ | `test_ac2_ac3_integration_add_to_processing_queue_blocks_new_message` PASS (yeni mesaj engellenirken devam eden işlemler etkilenmez) |
| AC-4 | ✅ | `test_ac4_hour_change_resets_counter` PASS |
| AC-5 | ✅ | `test_ac5_fail_open_missing_json_file` PASS |
| AC-6 | ✅ | `test_ac6_hourly_cap_exceeded_function_exists`, `test_ac6_module_level_variables_exist`, `test_ac6_exact_cap_limit_not_exceeded` PASS |

## CAVEMAN Değerlendirmesi
Yeni dosya yok, ayrı bir "ertelenmiş mesaj" veri yapısı icat edilmedi (plan.md'nin
kararına uygun), 3 yardımcı fonksiyon hepsi gerekçeli (saat anahtarı hesaplama,
restart-kurtarma, dış kontrol noktası).

## Sonraki Adım
`verify` — gerçek test/tam suite/lint geçitlerini çalıştıracak.
