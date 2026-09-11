# Test Diff — pm2-process-izleme-ve-uyari

> Codex kotası dolu; bu task'ta test/implementasyon istisnai olarak Claude
> tarafından yazıldı, kullanıcı onaylıdır (bkz. `saga` skill Bölüm C).

## Yeni Dosya
`tests/test_pm2_process_health.py` — 12 test, 3 sınıf.

## AC → Test Eşlemesi
| AC | Test | Kırmızı doğrulandı mı |
|---|---|---|
| AC-1 (hepsi online → ok) | `test_all_online_returns_ok_no_down_since` | ✅ |
| AC-2 (down ilk tespit, listede yok / stopped) | `test_missing_process_treated_as_down`, `test_stopped_status_treated_as_down`, `test_first_check_with_no_previous_history_down_process` | ✅ |
| AC-3 (down_since sabit kalır) | `test_down_since_preserved_across_repeated_down_checks` | ✅ |
| AC-4 (düzelme) | `test_recovered_process_clears_down_since` | ✅ |
| AC-5 (pm2 komutu başarısız → unknown, down değil) | `test_pm2_command_failed_marks_all_unknown_not_down` | ✅ |
| Parse helper (I/O ayrımı) | `test_parses_valid_jlist_output`, `test_subprocess_failure_returns_none`, `test_malformed_json_returns_none`, `test_empty_output_returns_none` | ✅ |
| `/api/status` yeni alan | `test_status_includes_process_health_field` | ✅ |

## Kırmızı Kanıt (implementasyon öncesi)
```
12 failed in 1.79s
AttributeError: <module 'src.api.admin_panel' ...> does not have the
attribute '_process_health'
```

## Yeşil Kanıt (implementasyon sonrası)
```
12 passed in 0.77s
```

## Regresyon Kontrolü
`test_deepseek_primary_balance_alert.py` + `test_deepseek_balance_diff_spend.py`
— 28 test, hepsi hâlâ yeşil. Mevcut `_status_cache`/`_refresh_status_cache`
davranışı (SERVICE_NAME'e özel `service` alanı) DEĞİŞMEDİ, sadece yanına
`_process_health` eklendi.

## Test Piramidi
Unit (11/12, ~%92): `_compute_process_health` (7), `_parse_pm2_jlist` (4)
Integration (1/12, ~%8): `/api/status` endpoint testi (gerçek Flask route)
E2E (0/12): Gerçek PM2'ye çağrı yapılmadı — ATDD'nin Test Strategy'sinde
zaten mock'lanmalı kararı verilmişti, gerçek doğrulama kullanıcının VPS'te
canlı gözlemine bırakıldı.

Not: ATDD hedefi (70/20/10) ile gerçekleşen (92/8/0) arasındaki fark, bu
görevin saf durum-hesaplama mantığı ağırlıklı olmasından kaynaklanıyor —
aynı desen `deepseek-balance-diff-maliyet-hesaplama` görevinde de
gözlemlendi.
