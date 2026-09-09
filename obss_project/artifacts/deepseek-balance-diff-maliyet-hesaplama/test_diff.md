# Test Diff — deepseek-balance-diff-maliyet-hesaplama

> Codex kotası dolu; bu task'ta test/implementasyon istisnai olarak Claude
> tarafından yazıldı, kullanıcı onaylıdır (bkz. `saga` skill Bölüm C).

## Yeni Dosya
`tests/test_deepseek_balance_diff_spend.py` — 15 test, 5 sınıf.

## AC → Test Eşlemesi
| AC | Test | Kırmızı doğrulandı mı |
|---|---|---|
| AC-1 (happy path, fark=harcama) | `test_happy_path_balance_decreased_returns_spend`, `test_balance_unchanged_no_top_up_no_spend`, `test_append_creates_file_and_appends_entries` | ✅ (implementasyon öncesi `AttributeError: DEEPSEEK_BALANCE_HISTORY_PATH` ile fail) |
| AC-2 (top-up → spend=0) | `test_balance_increased_top_up_detected_spend_zero` | ✅ |
| AC-3 (unknown → gap, referans bozulmaz) | `test_unknown_reading_marks_gap_no_spend_written`, `test_load_last_known_balance_skips_gap_entries`, `test_get_deepseek_real_spend_returns_none_when_last_entry_is_gap` | ✅ |
| AC-4 (ilk okuma → kayıt yok) | `test_first_reading_no_previous_balance_returns_none`, `test_unknown_reading_with_no_previous_balance_still_returns_none`, `test_load_last_known_balance_missing_file_returns_none`, `test_get_deepseek_real_spend_returns_none_when_no_history` | ✅ |
| AC-5 (`/status` yeni alan, mevcut alan değişmez) | `test_status_includes_deepseek_real_spend_field`, `test_get_deepseek_real_spend_returns_last_entry_spend` | ✅ |
| Davranış sözleşmesi satır 5 (yazma hatası çökertmemeli) | `test_append_write_failure_does_not_raise` | ✅ |
| Plan.md restart kurtarma | `test_load_last_known_balance_used_as_restart_reference` | ✅ |

## Kırmızı Kanıt (implementasyon öncesi çalıştırma)
```
15 failed in 1.63s
AttributeError: <module 'src.api.admin_panel' ...> does not have the
attribute 'DEEPSEEK_BALANCE_HISTORY_PATH'
```
(15 testin tamamı, henüz var olmayan `DEEPSEEK_BALANCE_HISTORY_PATH` /
`_compute_balance_diff` / `_append_deepseek_balance_history` /
`_load_last_known_deepseek_balance` / `_get_deepseek_real_spend`
isimlerine referans verdiği için fail etti — beklenen kırmızı durum.)

## Yeşil Kanıt (implementasyon sonrası)
```
15 passed in 0.65s
```

## Regresyon Kontrolü
Mevcut DeepSeek testleri (`test_deepseek_primary_balance_alert.py`,
`test_deepseek_cost_fix.py`, `test_deepseek_max_tokens_cap.py`) — 32 test,
hepsi hâlâ yeşil. `_check_deepseek_balance_once` dönüş şekli ve
`_deepseek_balance_cache` yapısı DEĞİŞMEDİ.

## Test Piramidi
Unit (13/15, ~%87): `_compute_balance_diff` (6), `_append_deepseek_balance_history`/`_load_last_known_deepseek_balance` (4), `_get_deepseek_real_spend` (3)
Integration (2/15, ~%13): `/api/status` endpoint testi (Flask test_request_context ile gerçek route çağrısı)
E2E (0/15): Gerçek DeepSeek API'ye çağrı yapılmadı — ATDD'de zaten "mock'lanmalı" kararı verilmişti.

Not: ATDD'nin hedef oranı (70/20/10) ile ölçülen oran (87/13/0) arasındaki
fark, bu görevin saf hesaplama mantığı ağırlıklı olmasından kaynaklanıyor
— e2e için gerçek DeepSeek çağrısı ATDD'nin "Kapsam Dışı" bölümünde zaten
hariç tutulmuştu.
