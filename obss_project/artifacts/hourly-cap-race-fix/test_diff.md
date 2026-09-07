# Test Diff — hourly-cap-race-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
- `tests/test_hourly_cap_race_condition.py` (yeni, 10 test, Haiku alt-ajanı tarafından yazıldı, mevcut `tests/test_hourly_spend_cap.py`'nin global-state reset desenini takip ederek)

## Kalite Düzeltmesi (orkestratör tarafından tespit edildi)
İlk yazımda `test_ac2_track_spend_resolves_reservation` ve `test_ac2_reserved_never_goes_negative` testleri `hasattr(...)`/`getattr(..., default)` kullanıyordu — `_current_hour_reserved_try` henüz kod tabanında yokken bu iki test hiçbir şey doğrulamadan sessizce PASS oluyordu (sahte-yeşil, gerçek bir red-step testi değildi). Bir Haiku alt-ajanına sertleştirme dispatch edildi: artık `assert hasattr(...)` ile attribute'un varlığı zorunlu kılınıyor, `_track_spend()` sonrası tam sayısal eşitlik (`abs(final - expected) < 0.001`) kontrol ediliyor. Doğrulama: `pytest tests/test_hourly_cap_race_condition.py -q` → **8 failed, 1 passed, 1 skipped**.

## Gerçek Çalıştırma (orkestratör tarafından doğrulandı)
```
python -m pytest tests/test_hourly_cap_race_condition.py -q
8 failed, 1 passed, 1 skipped in 3.91s
```

## AC -> Test Mapping
1. AC-1 (rezervasyon, race önleme) -> `test_ac1_sequential_50_calls_should_block_at_cap`, `test_ac1_concurrent_50_threads_respects_reservation_limit`, `test_integration_sequential_then_concurrent_consistency` -> RED (bekleniyor)
2. AC-2 (rezervasyon->gerçek maliyet düzeltmesi, negatife düşmeme) -> `test_ac2_track_spend_resolves_reservation`, `test_ac2_reserved_never_goes_negative` -> RED (bekleniyor, sertleştirme sonrası)
3. AC-3 (başarısız/timeout'ta rezervasyon geri alma) -> `test_ac3_release_hourly_reservation_decreases_reserved` (RED), `test_ac3_release_at_zero_does_not_go_negative` (SKIPPED — fonksiyon yok, implementasyon sonrası aktif olacak)
4. AC-4 (saat değişimi, her iki sayaç sıfırlanır) -> `test_ac4_hour_change_resets_reserved_and_cost` -> RED (bekleniyor)
5. AC-5 (fail-open) -> `test_ac5_exception_in_is_hourly_cap_exceeded_returns_false` (**PASS** — mevcut kod zaten fail-open, regresyon testi), `test_ac5_exception_in_track_spend_doesnt_crash` (RED — `_track_spend()`'de henüz try/except yok)

## Coverage / Quality Notes
- `test_ac3_release_at_zero_does_not_go_negative` şu an SKIPPED çünkü `release_hourly_reservation()` fonksiyonu hiç yok — implementasyon sonrası bu testin gerçekten çalışıp PASS olduğu `verify` adımında ayrıca doğrulanmalı, "skipped kaldı" görülmemeli.
- `test_ac5_exception_in_is_hourly_cap_exceeded_returns_false`'ın implementasyon öncesi PASS olması beklenen ve doğru — bu mevcut davranışın regresyon koruması, red-step testi değil.
