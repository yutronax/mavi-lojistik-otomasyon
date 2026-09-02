# Plan — kasa-tipi-eksik-fix
_Reference: atdd.md_

## Kod keşfi — atdd.md'nin Unknowns'ını netleştiren bulgular
- `data/yuk_tipi.json`: **2330 kural**, ama sadece **15 farklı KASA TİPİ değeri** (AÇIK, KAPALI, DAMPERLİ, FRİGO, LOWBED ve bunların kombinasyonları). Bu, atdd.md'nin şüphelendiği kural-kapsamı-eksikliği riskini doğruluyor — örn. bu oturumda canlı loglarda görülen "AÇIK TENTE"/"AÇIK TENTELİ" gibi çok yaygın bir Türkçe lojistik terimi bu 15 değerin hiçbirinde yok (TENTELİ ayrı bir kategori olarak hiç tanımlı değil, muhtemelen AÇIK'a düşürülüyor veya hiç eşleşmiyor).
- `tools/submit_approved_loads.py::transform_record_to_payload()` (satır 285+) shipment dict'ini YukBurada payload'ına **alan-alan, açık isim listesiyle (allowlist)** dönüştürüyor — blind pass-through DEĞİL. Bu, atdd.md'nin "Assumptions" bölümündeki riski (yeni flag alanlarının yanlışlıkla YukBurada'ya gönderilmesi) ÇÖZÜYOR: `kasa_tipi_belirsiz`/`kasa_tipi_belirsiz_sebep` alanları bu fonksiyon tarafından hiç referans alınmadığı için otomatik olarak payload'a sızmayacak — ek bir filtreleme koduna gerek YOK.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `src/utils/vehicle_type_matcher.py` | `find_all_matches()` şu an `None` veya `dict` dönüyor — AC-2/AC-3 gereği, hiç eşleşme yoksa "ipucu var mı yok mu" ayrımını yapıp bunu çağırana iletmesi gerekiyor. `find_match()`/`apply_to_shipment()` bu bilgiyi shipment'a taşıyacak şekilde güncellenmeli. | medium |
| `text_gen_parser.py` (satır ~705-738) | Rota oluşturma bloğu, `vehicle_matcher`'dan artık gelen flag/sebep bilgisini `route` dict'ine (`kasa_tipi_belirsiz`, `kasa_tipi_belirsiz_sebep`) eklemeli (AC-2, AC-3, AC-4). | medium |
| `data/eslesmeyen_kasa_ifadeleri.json` | Bu dosya YENİ oluşturulacak (aşağıda "New Files"), ama ona yazan kodun `text_gen_parser.py` veya `vehicle_type_matcher.py` içinde olması gerekiyor — yazma sorumluluğu plan aşamasında netleşmeli (Open Questions'a taşındı). | low |

## New Files
| File | Purpose |
|------|---------|
| `data/eslesmeyen_kasa_ifadeleri.json` | AC-3 gereği: mesajda kasa tipine dair bir ipucu var ama hiçbir kural eşleşmediğinde, ham metin parçası + zaman damgası + mesaj ID buraya biriktirilir. Format: JSON dizisi, her eleman `{"timestamp": ..., "msg_id": ..., "ham_metin": ...}`. |

## Dependencies
- `text_gen_parser.py`'nin zaten kullandığı `self.vehicle_matcher` (`VehicleTypeMatcher` örneği) — değişiklik bu örneğin metodlarına ek dönüş bilgisi kazandırmakla sınırlı, yeni bir bağımlılık eklenmiyor.
- Dosya yazma için mevcut proje deseni: `persistence_manager.queue_write()` (data_service.py'de kullanılan asenkron/kilitli yazma yardımcı fonksiyonu) `data/eslesmeyen_kasa_ifadeleri.json` için de kullanılmalı — CAVEMAN ilkesi gereği yeni bir dosya-yazma mekanizması İCAT EDİLMEMELİ, mevcut deseni tekrar kullan.
- `tools/submit_approved_loads.py::transform_record_to_payload()` — DEĞİŞTİRİLMİYOR (yukarıda açıklandığı gibi, allowlist mimarisi zaten yeni alanları otomatik filtreliyor, ek kod gerekmiyor).

## Migration Required?
Hayır. `data/eslesmeyen_kasa_ifadeleri.json` yeni bir dosya (şema göçü değil, yeni bir kayıt dosyası). Shipment dict'ine eklenen `kasa_tipi_belirsiz`/`kasa_tipi_belirsiz_sebep` alanları da bir "şema göçü" değil — mevcut JSON tabanlı, esnek şemalı kayıtlara (data/onaylanmamis_ayristirilmis.json vb.) yeni, opsiyonel alanlar ekliyor; okuma tarafında bu alanların yokluğu (eski kayıtlarda) hata vermemeli (`.get(..., False)` ile okunmalı).

## Risks
_(atdd.md'den taşındı + kod keşfinde netleşenler)_
- **"İpucu var ama eşleşmedi" tespitinin kesin algoritması** (atdd.md'nin en büyük Unknown'u) — aşağıda Open Questions'ta somutlaştırıldı, code-copilot başlamadan karar verilmeli.
- `data/yuk_tipi.json` 2330 kural içeriyor — bu dosyayı okuyup "bilinen kasa-tipi anahtar kelimeleri" listesi çıkarmak (Open Question'daki B seçeneği) biraz işlem gerektirir ama tek seferlik, mesaj başına tekrar hesaplanmasına gerek yok (sınıf `__init__`'inde bir kez çıkarılıp cache'lenebilir — CAVEMAN: yeni bir cache mekanizması icat etmek yerine, `VehicleTypeMatcher.__init__`'in zaten `_load_rules()` sırasında bunu bir kez hesaplayıp `self.known_kasa_keywords` gibi bir sete kaydetmesi yeterli, ayrı bir dosya/servis gerekmiyor).
- Fuzzy eşleştirme (`_match_pattern_in_tokens`) zaten karmaşık — flag eklerken bu fonksiyonun DAVRANIŞINI (eşleşme sonucunu) DEĞİŞTİRMEDEN, sadece "eşleşti mi" bilgisini `find_all_matches`'ın zaten döndürdüğü `matches_found` değişkeninden okuyup dışarı taşımak yeterli olmalı (bu değişken zaten fonksiyon içinde var, satır 253/321).

## Open Questions
1. **"İpucu var ama eşleşmedi" (AC-3) nasıl tespit edilecek?** İki seçenek:
   - **A (basit, önerilen):** `data/yuk_tipi.json`'daki TÜM `orjinal mesajdaki` pattern kelimelerinden benzersiz bir "bilinen kasa-tipi anahtar kelimeler" seti çıkar (`VehicleTypeMatcher.__init__`'te bir kez, cache'lenmiş). Mesaj metninde bu kelimelerden biri geçiyor AMA `find_all_matches` sonucu `None`/boşsa → `"kural_eslesmedi"`. Hiçbiri geçmiyorsa → `"ipucu_yok"`.
   - **B (daha karmaşık):** Sabit, elle yazılmış bir "bilinen kasa tipi kelimeleri" listesi (FRİGO, DAMPERLİ, TENTELİ, AÇIK, KAPALI, LOWBED, PLATFORM...) tutup mesajı buna karşı tara.
   - Seçenek A, CAVEMAN ilkesine daha uygun (veri zaten dosyada var, elle liste bakımı gerekmiyor) — **öneri: A**, ama code-copilot başlamadan onaylanmalı.
2. **`data/eslesmeyen_kasa_ifadeleri.json`'a yazma sorumluluğu nerede olmalı?** `vehicle_type_matcher.py` (matcher kendi başarısızlığını loglar, `text_gen_parser.py`'den bağımsız, daha temiz katman ayrımı) mı, yoksa `text_gen_parser.py`'nin rota oluşturma bloğu mu (zaten `msg_id`/zaman bilgisine orada erişim var)? **Öneri:** `text_gen_parser.py` — çünkü `msg_id` ve tam mesaj bağlamı orada mevcut, `vehicle_type_matcher.py`'nin bu bilgilere erişimi yok (sadece ham metin string'i alıyor).
3. **Panelde (`admin_panel.py`) görsel gösterge bu görevde mi eklenecek, yoksa sadece backend flag'i mi yeterli?** atdd.md bunu "Kapsam Dışı"na koşullu olarak koymuştu. **Öneri:** Bu görevde SADECE backend flag'i + log dosyası yeterli (AC'lerin hiçbiri panel UI değişikliği talep etmiyor) — panel gösterimi ayrı, küçük bir takip görevi olarak bırakılsın.

## Kararlar
1. **Seçenek A** — `data/yuk_tipi.json`'daki pattern kelimelerinden `VehicleTypeMatcher.__init__`'te bir kez çıkarılıp cache'lenen "bilinen kasa-tipi anahtar kelimeler" seti kullanılacak. (Haiku alt-ajanı tarafından yanıtlandı: elle bakım gerektirmeyen, veri kaynağından türeyen, tek seferlik maliyetli çözüm — CAVEMAN'a uygun.)
2. **`text_gen_parser.py`'nin rota oluşturma bloğu** eşleşmeyen ifadeleri `data/eslesmeyen_kasa_ifadeleri.json`'a yazacak. (Haiku alt-ajanı tarafından yanıtlandı: msg_id ve mesaj bağlamı zaten orada mevcut, `vehicle_type_matcher.py`'nin bu meta-bilgilere erişimi yok.)
3. **Sadece backend flag'i + log dosyası** — panel UI değişikliği bu görevde YAPILMAYACAK. (Haiku alt-ajanı tarafından yanıtlandı: AC'lerin hiçbiri panel değişikliği talep etmiyor, ayrı bir takip görevi olarak bırakılıyor.)
