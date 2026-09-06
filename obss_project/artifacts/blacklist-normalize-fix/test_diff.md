# Test Diff — blacklist-normalize-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
- `tests/test_blacklist_normalize.py` (yeni, 24 test, Haiku alt-ajanı tarafından yazıldı)

## AC -> Test Mapping
1. AC-1 (normalize+kayıt) -> `test_normalize_phone_with_spaces_ac1`, `test_normalize_phone_with_dashes_ac1`, `test_normalize_phone_with_plus_and_spaces_ac1`, `test_add_blacklist_normalizes_and_saves_ac1`, `test_save_and_load_normalized_blacklist_ac1_ac3` -> çoğu PASS, implementasyon sonrası da PASS kalmalı
2. AC-2 (is_phone_in_list normalize eşleşme + reason ayrı saklama) -> `test_is_phone_in_list_with_unnormalized_in_list_ac1_ac2` (RED — bekleniyor), `test_add_blacklist_with_reason_saves_separately_ac2` -> code-copilot sonrası ilk test PASS olmalı
3. AC-3 (VPS regresyon, düz-string format bozulmamalı) -> `test_is_phone_in_list_with_normalized_list_ac3`, `test_vps_existing_blacklist_still_matches_ac3`, `test_save_and_load_normalized_blacklist_ac1_ac3` -> zaten PASS, code-copilot sonrası da PASS kalmalı (regresyon garantisi)
4. AC-4 (duplicate tespiti) -> `test_normalize_produces_same_for_different_formats_ac4`, `test_add_blacklist_detects_duplicate_ac4` -> PASS
5. AC-5 (geçersiz numara reddi) -> `test_normalize_phone_invalid_too_short_ac5`, `test_normalize_phone_invalid_too_long_ac5`, `test_add_blacklist_rejects_invalid_short_phone_ac5` (RED — bekleniyor), `test_add_blacklist_rejects_invalid_long_phone_ac5` (RED — bekleniyor)
6. AC-6 (karışık string+dict coercion, save_blacklist crash etmemeli) -> `test_is_phone_in_list_with_dict_entries_ac6` (RED — bekleniyor), `test_save_blacklist_with_dict_entries_no_crash_ac6`, `test_save_blacklist_coerces_to_normalized_strings_ac6`

## Şu An Kırmızı (Red) Olan Testler — code-copilot bunları yeşile çevirecek
1. `test_is_phone_in_list_with_unnormalized_in_list_ac1_ac2` — `is_phone_in_list()` boşluklu/tireli phone_list elemanlarını normalize etmiyor.
2. `test_is_phone_in_list_with_dict_entries_ac6` — `is_phone_in_list()` dict formatlı elemanları hiç işlemiyor.
3. `test_add_blacklist_rejects_invalid_short_phone_ac5` — `normalize_phone()` çok kısa girdilerde boş/geçersiz döndürmüyor, reddetme mantığı yok.
4. `test_add_blacklist_rejects_invalid_long_phone_ac5` — `normalize_phone()` çok uzun girdilerde de aynı sorun.

## Coverage / Quality Notes
- Haiku alt-ajanının raporuna göre 24 testten 20'si **şimdiden PASS** — bunların bir kısmı gerçek "red step" testi değil, mevcut/hedeflenen davranışı belgeleyen (spec-documenting) testler (ör. `save_blacklist` zaten dict ile çağrılmadığı senaryoları mock'layan testler). Bu, test-first disiplinini tam karşılamıyor: ideal olan AC-2/AC-6/AC-5'in TÜMÜNÜN implementasyon öncesi kırmızı olmasıydı.
- `code-copilot`'tan sonra `verify` adımında tüm 24 testin (sadece 4 değil) gerçekten çalıştırılıp PASS olduğu doğrulanmalı — özellikle "PASS" olarak işaretlenen ama aslında zayıf/triviyal assertion içerebilecek testler (`test_save_blacklist_with_dict_entries_no_crash_ac6` gibi mock-ağırlıklı olanlar) gerçek `data_service.save_blacklist()` ile de doğrulanmalı.
- Davranış Sözleşmesi tablosunun satır 3 (kaynak yok/silme) ve satır 5 (Mongo sync hatası) için ayrı test yazılmadı — mevcut davranış korunacağı için (atdd.md'de "mevcut davranış korunur" notu var) bu görev kapsamında yeni test gerekmediği kabul edildi, ama `verify` bunu N/A olarak işaretlemeli, sessizce atlamamalı.
