# Code Diff — hourly-cap-race-fix
_Reference: atdd.md, plan.md, test_diff.md_

## Değiştirilen Dosyalar (doğrulanmış)
- `text_gen_parser.py` (123 satır ekleme, 60 satır çıkarma)
- `tests/test_hourly_spend_cap.py` (mevcut testin state-sızıntısı regresyonu düzeltildi — bkz. aşağıda)

## Değişikliklerin Özeti (Read ile doğrulandı)
- `_current_hour_reserved_try = 0.0` yeni global + `ESTIMATED_COST_PER_CALL_TRY = 0.20` sabiti (DeepSeek ortalama fiyatlandırmasından türetildi, yorum satırında hesaplama gösteriliyor).
- `is_hourly_cap_exceeded()`: artık `_hourly_lock` altında atomik "kontrol+rezerve" yapıyor — `cost + reserved > cap` ise rezerve etmeden `True`, aksi halde `reserved += ESTIMATED_COST_PER_CALL_TRY` yapıp `False` döner. Saat değişimi aynı fonksiyon içinde hem `cost` hem `reserved`'i sıfırlıyor.
- `release_hourly_reservation()`: yeni fonksiyon, `max(0.0, reserved - ESTIMATED_COST_PER_CALL_TRY)` ile rezervasyonu geri alır.
- `_track_spend()`: artık tam bir `try/except` ile sarılı (AC-5 fail-open), gerçek maliyet eklenmeden önce bir rezervasyon birimini serbest bırakıyor.
- `parse_async()`: iki erken çıkış noktasına (`hallucination protection` ve `tüm modeller tükendi`) `release_hourly_reservation()` çağrısı eklendi.

## Code-Copilot Sonrası Düzeltme #1 — Regresyon (orkestratör tarafından tespit edildi)
İlk implementasyon turunda `tests/test_hourly_spend_cap.py`'deki mevcut bir test (`test_ac6_exact_cap_limit_not_exceeded`) dosyanın TAMAMI çalıştırıldığında FAIL etmeye başladı (tek başına PASS) — kök neden: bu test dosyası yeni `_current_hour_reserved_try` global'ini hiç patch/reset etmiyordu, önceki testlerin bıraktığı rezervasyon state'i sızıyordu. Sub-agent bunu "test fixture sorunu, implementasyon değil" diye nitelendirdi; bu iddia bağımsız olarak doğrulandı (`pytest tests/test_hourly_spend_cap.py -k exact_cap` tek başına PASS, dosyanın tamamıyla FAIL — klasik state-sızıntısı imzası). Düzeltme: mevcut test dosyasındaki 6 test fonksiyonuna (8 `patch.object` çağrısı) `_current_hour_reserved_try` izolasyonu eklendi. Doğrulama: `pytest tests/test_hourly_spend_cap.py tests/test_hourly_cap_race_condition.py -q` → **20 passed**.

## Code Smell — Red-Team'e Taşınacak (orkestratör tarafından tespit edildi, düzeltilmedi)
`_init_hourly_counter_from_file()`'a eklenen yeni dal:
```python
if not os.path.exists(spend_file):
    # Test mode: dosya yok, sadece hour_key'i set et (test patch'lemesine müdahale etme)
    _current_hour_key = hour_key
    return
```
Yorum satırı açıkça test senaryosuna göre yazılmış ("test patch'lemesine müdahale etme") — prod kodu testin varlığını biliyormuş gibi davranıyor, bu kötü bir desen. **Fonksiyonel olarak zararsız**: gerçek üretimde dosya yoksa (`data/ai_spend_history.json` ilk saatte henüz oluşmamışsa) `_current_hour_cost_try` zaten modül yüklenirken `0.0` olarak başlıyor, bu dal onu değiştirmiyor sadece `_current_hour_key`'i set edip erken dönüyor — sonuç aynı (0.0). Ama çerçeveleme/yorum yanlış ve bakım riski taşıyor (gelecekte biri bu "test mode" mantığına güvenip üzerine yanlış bir varsayım inşa edebilir). Bu, `red-team` incelemesine bir bulgu olarak aktarılacak — düzeltme kararı (yorum/çerçeveleme düzeltmesi mi, yoksa daha temiz bir yeniden yazım mı) red-team sonrası verilecek.

## Acceptance Criteria Karşılama
| AC | Durum | Kanıt |
|----|-------|-------|
| AC-1 | Karşılandı | `is_hourly_cap_exceeded()` atomik kontrol+rezerve, `test_ac1_sequential_50_calls_should_block_at_cap`, `test_ac1_concurrent_50_threads_respects_reservation_limit` PASS |
| AC-2 | Karşılandı | `_track_spend()` rezervasyon çözme + `max(0.0,...)`, `test_ac2_track_spend_resolves_reservation`, `test_ac2_reserved_never_goes_negative` PASS |
| AC-3 | Karşılandı | `release_hourly_reservation()` + `parse_async()`'in 2 çıkış noktasında çağrılıyor, `test_ac3_*` PASS |
| AC-4 | Karşılandı | Saat değişimi her iki sayacı sıfırlıyor, `test_ac4_hour_change_resets_reserved_and_cost` PASS |
| AC-5 | Karşılandı | `_track_spend()` artık try/except ile sarılı, `is_hourly_cap_exceeded()` zaten fail-open, `test_ac5_*` PASS |

## Gerçek Test Çalıştırması (orkestratör tarafından, sub-agent özetine güvenilmedi)
```
python -m pytest tests/test_hourly_spend_cap.py tests/test_hourly_cap_race_condition.py -q
20 passed in 3.61s
```

## Definition of Done Kontrolü
- TODO/FIXME/placeholder yok.
- `is_hourly_cap_exceeded()`'ın imzası (parametresiz, bool) değişmedi — `veri_cekici_ayristirici.py`'ye dokunulmadı (`git diff --stat` ile doğrulandı, sadece `text_gen_parser.py` ve test dosyası değişti).
- `_track_spend()`'in mevcut çağrı yerleri (satır 472, 487, 509 civarı) değişmedi.
- Yukarıdaki "code smell" istisnası dışında ölü kod/gereksiz soyutlama yok.

## Kalan Sınırlamalar
- `_init_hourly_counter_from_file()`'daki "test mode" çerçevelemesi red-team'e bulgu olarak taşınıyor (yukarıda detaylı).
- `ESTIMATED_COST_PER_CALL_TRY = 0.20` sabit bir tahmin — gerçek ortalama maliyetten sapabilir, atdd.md'nin Risks bölümünde zaten kabul edilen bir sınırlama (mükemmel doğruluk garantisi yok, öngörülebilir küçük bir tolerans hedefleniyor).
