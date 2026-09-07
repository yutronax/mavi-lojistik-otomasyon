# Plan — hourly-cap-race-fix
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| text_gen_parser.py | `is_hourly_cap_exceeded()` (satır 81-93) atomik "kontrol+rezerve" yapacak şekilde değiştirilecek; `_track_spend()` (satır 152-201) gerçek maliyet geldiğinde rezervasyonu çözecek şekilde güncellenecek; `parse_async()`'in tüm-modeller-tükendi başarısızlık noktasına (satır 602-605, `return []`'dan hemen önce) rezervasyonu geri alan bir çağrı eklenecek. | medium |

## New Files
| File | Purpose |
|------|---------|
| tests/test_hourly_cap_race_condition.py | AC-1..AC-5'i kapsayan thread-safety + unit testler: 50 eşzamanlı `is_hourly_cap_exceeded()` çağrısının rezervasyonu doğru sınırladığını, `_track_spend`'in rezervasyonu doğru çözdüğünü, başarısız/timeout senaryosunda rezervasyonun geri alındığını, sayacın negatife düşmediğini, fail-open davranışının korunduğunu doğrular. |

## Dependencies
- Mevcut `_hourly_lock` (`threading.Lock`, zaten global) — hem `is_hourly_cap_exceeded()` hem `_track_spend()` hem yeni `release` fonksiyonu AYNI lock'u kullanacak, yeni bir senkronizasyon mekanizması eklenmeyecek (atdd.md Assumptions/Edge case 2).
- Mevcut `_current_hour_key`, `_current_hour_cost_try` global değişkenleri — yanına yeni bir `_current_hour_reserved_try` (pending rezervasyon toplamı) global değişkeni eklenecek.
- `_get_current_hour_key()` (satır 55-57) — saat değişimi tespiti, hem gerçek maliyet hem rezervasyon sayaçlarının aynı anda sıfırlanması gerekecek (mevcut `_init_hourly_counter_from_file`/`is_hourly_cap_exceeded`'daki saat-değişimi mantığı genişletilecek).

## Tasarım (kod keşfiyle netleşti — atdd.md'nin "Unknowns" bölümünü çözüyor)
`parse_async()` (satır 317-605) okundu: AI çağrısı, retry döngüsü (3 deneme × birden fazla model) ve `_track_spend()` çağrıları TAMAMEN bu fonksiyonun içinde, `text_gen_parser.py`'de. `veri_cekici_ayristirici.py` sadece `is_hourly_cap_exceeded()`'ı (parametresiz, dönüş değeri bool) çağırıyor — bu imza değişmeyecek, atdd.md'nin Kapsam Dışı kararı ("veri_cekici_ayristirici.py'ye dokunulmayacak") tam olarak uygulanabilir.

Mekanizma:
1. **Rezervasyon (AC-1):** `is_hourly_cap_exceeded()` artık `_hourly_lock` altında: `if _current_hour_cost_try + _current_hour_reserved_try >= cap: return True` (rezerve etmeden). Aksi halde `_current_hour_reserved_try += ESTIMATED_COST_PER_CALL_TRY` yapıp `False` döner. `ESTIMATED_COST_PER_CALL_TRY` sabiti, `_track_spend`'teki mevcut fiyat sabitlerinden (DeepSeek $0.27/$1.10 per 1M, ortalama ~1000 input+300 output token varsayımıyla) türetilecek, tek bir modül-seviyesi sabit olarak.
2. **Çözme/Düzeltme (AC-2):** `_track_spend()` gerçek `cost_try` hesaplandığında: `_current_hour_reserved_try = max(0.0, _current_hour_reserved_try - ESTIMATED_COST_PER_CALL_TRY)` (bir rezervasyon birimini serbest bırak) + `_current_hour_cost_try += cost_try` (gerçek maliyeti ekle). Bir mesajda birden fazla model denemesi gerçek maliyet üretirse (her biri kendi `_track_spend`'ini çağırır), ilk çağrı rezervasyonu serbest bırakır, sonrakiler `max(0.0, ...)` sayesinde negatif rezervasyona düşürmez — sadece gerçek maliyeti ekler (muhafazakâr, asla gerçek harcamayı eksik saymaz).
3. **Geri Alma (AC-3):** `parse_async()`'in satır 602-605'teki "tüm modeller tükendi" başarısızlık noktasına, `return []`'dan hemen önce, yeni bir `release_hourly_reservation()` fonksiyonu çağrılacak — bu, `_current_hour_reserved_try`'ı bir birim daha azaltır (`max(0.0, ...)`). Eğer bu mesaj için zaten bir `_track_spend` çağrısı olduysa (kısmi başarı — bir model cevap verdi ama sonuç geçersizdi) rezervasyon zaten adım 2'de serbest bırakılmış olacağı için bu çağrı no-op olur (güvenli, çift düşme riski `max(0.0,...)` ile önleniyor).
4. **Saat değişimi (AC-4):** Hem `_current_hour_cost_try` hem `_current_hour_reserved_try` aynı `hour_key` kontrolüyle birlikte sıfırlanacak (mevcut mantığın genişletilmesi, davranış değişmiyor).
5. **Fail-open (AC-5):** Yeni kod da mevcut `try/except` + `return False` (fail-open) desenini koruyacak — rezervasyon/düzeltme mantığında beklenmeyen bir hata olursa mesaj engellenmeyecek.

## Migration Required?
Hayır — sadece in-memory global state (mevcut `_current_hour_cost_try` gibi), veri tabanı/dosya şeması değişmiyor.

## Risks
- (atdd.md'den taşındı) `ESTIMATED_COST_PER_CALL_TRY` gerçek ortalama maliyetten çok farklıysa (çok düşük tahmin edilirse) race window küçülür ama sıfırlanmaz — bu görev "aşımı öngörülebilir küçük bir paya indirmeyi" hedefliyor, mükemmel doğruluk garantisi vermiyor (gerçek maliyet API cevabı gelmeden bilinemez, fiziksel bir sınır).
- Bir mesajın `parse_async()`'i içinde birden fazla model denemesi gerçek maliyet üretirse (örn. ilk model geçersiz JSON döndürüp bir sonraki model denenirse), İKİNCİ modelin maliyeti de sayaca eklenir ama rezervasyon SADECE BİR KEZ serbest bırakılır — bu, o mesaj için TEK bir rezervasyon biriminin doğru şekilde "kullanılmış" sayılmasını sağlar, gerçek toplam maliyet asla eksik sayılmaz (muhafazakâr/güvenli taraf).
- `release_hourly_reservation()`'ın `parse_async()`'in SADECE satır 602-605'teki (tüm modeller tükendi) çıkış noktasına eklenmesi yeterli mi, yoksa `RuntimeError`/`"interpreter shutdown"` (satır 553-556) gibi diğer erken `return []` noktalarına da mı eklenmeli? **Açık soru — aşağıda.**

## Open Questions (Kararlar)
1. **Çözüldü (Read ile, alt-ajana gerek kalmadı):** `parse_async()`'te üç farklı erken çıkış noktası var: (a) satır 335-337 hallucination protection (`return []`) — bu noktada AI çağrısı HİÇ yapılmamış, dolayısıyla rezervasyon henüz yapılmamış bile olabilir (bu nokta `is_hourly_cap_exceeded()` çağrısından SONRA ama AI çağrısından ÖNCE olduğu için rezervasyon zaten yapılmış durumda — bu çıkışta da `release_hourly_reservation()` çağrılmalı, aksi halde hiç AI çağrısı yapılmayan mesajlar için rezervasyon boşuna sayaçta kalır). (b) satır 553-556 `RuntimeError`/interpreter shutdown — nadir, süreç kapanırken oluşan bir durum, rezervasyon zaten anlamsızlaşacağı (süreç kapanıyor) için buraya release eklemek gereksiz karmaşıklık (CAVEMAN). (c) satır 602-605 tüm modeller tükendi — ZORUNLU release noktası. **Karar: release_hourly_reservation() hem (a) hem (c) noktasına eklenecek, (b) atlanacak** (süreç zaten kapanıyor, sayaç durumu önemsiz).
