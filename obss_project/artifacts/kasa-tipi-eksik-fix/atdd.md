---
task_slug: kasa-tipi-eksik-fix
jira_id: null
saga_task_id: null
priority: high
coverage_target: 80
performance_target: "flag/log ekleme find_match() çağrı sayısını artırmamalı, gözle görülür gecikme olmamalı"
memory_target: null
test_strategy:
  unit: 70
  integration: 20
  e2e: 10
affected_modules:
  - src/utils/vehicle_type_matcher.py (find_all_matches/find_match/apply_to_shipment — flag üretimi)
  - text_gen_parser.py (satır ~705-738, shipment oluşturma, kasa_tipi_belirsiz alanı ekleme)
  - data/yuk_tipi.json (kural kapsamı — bu görevde SADECE okunup denetlenecek, büyük genişletme kapsam dışı)
  - src/api/admin_panel.py (opsiyonel: panelde belirsiz kasa tipi göstergesi — Unknown, netleşmeli)
---

# ATDD — kasa-tipi-eksik-fix

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev.

## Persona
Panel operatörü — WhatsApp'tan gelen yük ilanlarını onaylayan/izleyen kişi. Yanlış/belirsiz kasa tipiyle giden bir ilanı ilan onaylama akışında fark etmesi gerekiyor. *(Haiku alt-ajanı tarafından yanıtlandı: son müşteri için fark etmek çok geç olur.)*

## Hedef (Neden)
`kasa_tipi` alanı AI modelinden değil, `src/utils/vehicle_type_matcher.py`'deki kural-tabanlı bir eşleştiriciden geliyor. Mesajın ilgili satırı `data/yuk_tipi.json`'daki hiçbir kural pattern'iyle eşleşmezse, sistem **sessizce** genel bir varsayılana (`kasa_tipi = ['AÇIK', 'KAPALI']`) düşüyor — hiçbir log/işaret bırakmadan. Bu, mesajda açıkça "FRİGO" veya "DAMPERLİ" gibi bir tip belirtilse bile kural tablosu bunu tanımıyorsa, YANLIŞ/BELİRSİZ bir kasa tipiyle ilan gönderilmesine yol açabiliyor — ve şu an hangi ilanların gerçek/net kasa tipiyle, hangilerinin sessiz varsayılanla gittiğini ayırt etmek MÜMKÜN DEĞİL. Hedef: bu sessiz düşüşü **görünür/tespit edilebilir** hale getirmek (flag + log), böylece hem operatör hangi ilanların şüpheli olduğunu görebilsin hem de zamanla `data/yuk_tipi.json`'a hangi eksik kalıpların eklenmesi gerektiği ortaya çıksın. *(Haiku alt-ajanı tarafından yanıtlandı: önce görünürlük, kural genişletme ayrı ve sürekli devam eden bir çaba.)*

## User Story
As a panel operatörü
I want kasa tipi belirsiz/varsayılan olarak atanmış ilanları ayırt edebilmek
So that yanlış kasa tipiyle YukBurada'ya giden ilanları fark edip düzeltebileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given bir mesajın ilgili satırı `yuk_tipi.json`'daki bir kuralla (tam veya fuzzy eşik ≥%80) eşleşiyor, When `find_all_matches`/`apply_to_shipment` çalışır, Then mevcut davranış AYNEN korunur — `kasa_tipi` kural çıktısına eşit olur, hiçbir belirsizlik flag'i eklenmez (regresyon yok).
2. [Critical] Given bir mesajın ilgili satırında kasa tipine dair HİÇBİR ipucu yok (kullanıcı hiç belirtmemiş), When kural eşleşmesi boş dönerse, Then `kasa_tipi` yine genel varsayılana (`['AÇIK', 'KAPALI']`) düşer AMA shipment'a `kasa_tipi_belirsiz: true` ve `kasa_tipi_belirsiz_sebep: "ipucu_yok"` alanları eklenir.
3. [Critical] Given bir mesajda kasa tipine dair bir ipucu VAR (ör. "FRİGO", "DAMPERLİ" gibi bir kelime metinde geçiyor) ama `yuk_tipi.json`'daki hiçbir kural buna eşleşmiyor (kural kapsam eksikliği), When bu durum tespit edilir, Then `kasa_tipi` yine genel varsayılana düşer, `kasa_tipi_belirsiz: true` ve `kasa_tipi_belirsiz_sebep: "kural_eslesmedi"` eklenir, VE eşleşmeyen ham metin parçası ayrı bir log/kayıt dosyasına (`data/eslesmeyen_kasa_ifadeleri.json`) yazılır (zaman damgası + ham metin + mesaj ID).
4. [High] Given bir mesajda birden fazla rota (sevkiyat) var, When her rota işlenir, Then her rotanın `kasa_tipi_belirsiz` durumu BAĞIMSIZ değerlendirilir — bir rota net kasa tipiyle, başka bir rota belirsiz flag'iyle aynı mesajdan çıkabilir.
5. [Medium] Given `data/eslesmeyen_kasa_ifadeleri.json` dosyası büyüdükçe, When bu dosya okunursa, Then en sık tekrar eden eşleşmeyen ifadeler görülebilir olmalı (kayıt şeması sıralama/gruplama için yeterli bilgi — ham metin + sayaç ya da her oluşta ayrı satır — içermeli; bu görevde otomatik bir "en sık eksik kalıplar" raporu YAZILMIYOR, sadece ham veri toplanıyor).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: kasa tipi net + kural eşleşti | `kasa_tipi = [rule_value]` | Yok (mevcut davranış) | Panelde normal ilan, flag yok | AC-1 |
| 2 | Kasa tipi belirsiz (mesajda hiç ipucu yok) | `kasa_tipi = ['AÇIK','KAPALI']`, `kasa_tipi_belirsiz: true`, `kasa_tipi_belirsiz_sebep: "ipucu_yok"` | Shipment dict'ine 2 yeni alan eklenir | Panelde (ileride) ayrı bir işaret görülebilir | AC-2 |
| 3 | Kasa tipi belirtilmiş ama kural eşleşmedi | `kasa_tipi = ['AÇIK','KAPALI']`, `kasa_tipi_belirsiz: true`, `kasa_tipi_belirsiz_sebep: "kural_eslesmedi"` | Shipment'a flag eklenir + `data/eslesmeyen_kasa_ifadeleri.json`'a kayıt düşülür | Aynı, ayrıca geliştirici zamanla eksik kuralları görebilir | AC-3 |
| 4 | Kısmi başarı: çok rotalı mesajda bazı rotalar net bazıları belirsiz | Her rota kendi `kasa_tipi_belirsiz` değerini taşır | Yok (ekstra) | Panelde bazı rotalar flag'li, bazıları değil | AC-4 |
| 5 | Hiçbir şey yapılamadı ama hata yok | Bu görevde `find_all_matches` zaten `None` dönebiliyor (mevcut davranış) — bu durum AC-2/AC-3'ün kapsadığı "ipucu yok" ile AYNI, ayrı bir satır gerekmiyor | — | — | *(AC-2 ile birleştirildi, tekrar olmasın diye silindi)* |
| 6 | Boş sonuç ↔ hata ayrımı | `kasa_tipi_belirsiz_sebep` alanı bu ayrımı zaten sağlıyor (`"ipucu_yok"` vs `"kural_eslesmedi"`) — üçüncü bir "hata" durumu bu görevde YOK (find_match exception fırlatmıyor, sadece None/dict dönüyor) | — | — | AC-2, AC-3 |

Kısmi başarı: Her rota bağımsız değerlendirilir (satırın kendi bağlamı `route_context`'e göre) — bir mesajdaki rotalardan biri net kasa tipiyle, diğeri belirsiz flag'iyle çıkabilir, bu NORMAL ve beklenen davranıştır.
Hiçbir şey yapılamadı ama hata yok: Bu görevde ayrı bir senaryo değil — "ipucu yok" (AC-2) durumuyla aynı, sessiz varsayılan yerine artık flag'li varsayılan dönüyor.
Boş sonuç ↔ hata ayrımı: `kasa_tipi_belirsiz_sebep` alanının iki değeri (`"ipucu_yok"` / `"kural_eslesmedi"`) bu ayrımı sağlıyor — "hiç bilgi yok" ile "bilgi var ama sistem tanımadı" birbirinden ayrılabiliyor.

## Test Strategy
Unit: 70% — `VehicleTypeMatcher.find_all_matches()`/`find_match()`'in flag/sebep bilgisini doğru döndürmesi (üç senaryo: net eşleşme, ipucu yok, ipucu var ama eşleşmedi), `apply_to_shipment()`'ın shipment dict'ine doğru alanları eklemesi.
Integration: 20% — `text_gen_parser.py`'nin `_process_raw_json_async` akışında (satır ~705-738) çok rotalı bir mesajın her rotasının bağımsız flag taşıdığının doğrulanması, `data/eslesmeyen_kasa_ifadeleri.json`'a gerçekten yazıldığının doğrulanması (geçici dizinde, gerçek dosyaya yazmadan).
E2E: 10% — Gerçek/örnek bir mesajla (net kasa tipi + belirsiz kasa tipi karışık) uçtan uca bir doğrulama.

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: Flag/log ekleme mevcut `find_match()` çağrı sayısını artırmamalı, mesaj işleme süresine gözle görülür gecikme eklenmemeli.
Diğer ölçülebilir kriterler:
- Mevcut (kural eşleşen) ilanların `kasa_tipi` çıkarım doğruluğunda REGRESYON OLMAMALI (AC-1 ile korunuyor).
- Operatör 3-5 gün panelde "belirsiz kasa tipi" oranını gözlemleyip bu görevi onaylar (otomatik ölçülemez, kullanıcı onayı gerekli).
- `data/eslesmeyen_kasa_ifadeleri.json`'da gerçek/anlamlı eşleşmeyen ifadeler birikmeye başlamalı (bu görevin başarı kanıtı: dosya gerçek veri toplarken sistemin geri kalanını bozmuyor olması).

## Kapsam Dışı
- `data/yuk_tipi.json`'a onlarca yeni kural eklemek gibi büyük bir veri-genişletme çalışması — bu görev SADECE görünürlük/tespit mekanizması kuruyor, kural genişletme ayrı ve sürekli devam eden bir görev olarak bırakılıyor. *(Haiku alt-ajanı tarafından yanıtlandı)*
- AI modelinin (Groq/DeepSeek) doğrudan `kasa_tipi` alanı üretecek şekilde yeniden tasarlanması — mevcut rule-based mimari korunuyor.
- `data/eslesmeyen_kasa_ifadeleri.json`'dan otomatik "en sık eksik kalıplar" raporu üretmek (AC-5'te not edildiği gibi, bu görevde sadece ham veri toplanıyor, raporlama ayrı bir görev).
- Panelde (`admin_panel.py`) yeni bir UI göstergesi/sütun eklemek — bu ATDD'de "etkilenen modüller"de opsiyonel olarak listelendi ama plan adımında netleşmezse bu görevin ilk sürümünde YAPILMAYABİLİR (backend flag'i üretmek yeterli, panel gösterimi ayrı bir küçük görev olabilir — plan adımında karar verilmeli).

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/utils/vehicle_type_matcher.py` — `find_all_matches`, `find_match`, `apply_to_shipment` (flag/sebep üretimi)
- `text_gen_parser.py` — satır ~705-738 (shipment oluşturma akışı, yeni alanların shipment dict'ine eklenmesi)
- `data/yuk_tipi.json` — bu görevde SADECE okunup denetlenecek (kural sayısı, mevcut kategori listesi — plan adımında teyit edilmeli, bu incelemede detaylı taranmadı)
- `data/eslesmeyen_kasa_ifadeleri.json` — YENİ dosya, eşleşmeyen ham ifadelerin biriktiği kayıt
- `src/api/admin_panel.py` — opsiyonel, netleşmemiş (bkz. Kapsam Dışı)

## Rollback Beklentisi
Yeni flag/loglama mekanizması hatalı çalışırsa (ör. her ilanı yanlışlıkla "belirsiz" işaretlerse), mevcut `kasa_tipi` DEĞERİ/DAVRANIŞI değişmediği için ilan akışı bozulmaz — sadece ek bilgi alanları (`kasa_tipi_belirsiz`, `kasa_tipi_belirsiz_sebep`) yanlış olabilir, bu da geri alınabilir/görmezden gelinebilir bir durumdur. *(Haiku alt-ajanı tarafından yanıtlandı)*

## Risks
- `data/yuk_tipi.json`'ın gerçek boyutu/kapsamı (kaç kural var, hangi kasa tipi kategorilerini kapsıyor: FRİGO, DAMPERLİ, LOWBED, AÇIK, KAPALI, TENTELİ vb.) bu incelemede detaylı taranmadı — plan/code-copilot adımında dosya okunarak teyit edilmeli. *(Haiku alt-ajanı tarafından yanıtlandı)*
- `_match_pattern_in_tokens`'ın fuzzy eşleşme mantığı (Levenshtein + %80 eşik) karmaşık — flag/sebep eklerken bu mantığın YANLIŞLIKLA değiştirilmemesi (sadece "eşleşti mi eşleşmedi mi" bilgisinin dışarı taşınması) önemli, mevcut eşleştirme davranışı bozulmamalı.
- "İpucu var ama eşleşmedi" (AC-3) tespiti, mesaj metninde kasa-tipi-benzeri bir kelime olup olmadığını nasıl anlayacağımız net değil (basit bir anahtar kelime listesi mi, yoksa "hiç eşleşme yoksa her zaman kural_eslesmedi say, aksi halde ipucu_yok" mu?) — bu ayrım plan adımında netleştirilmeli.

## Assumptions
- Shipment dict'ine yeni alan eklemenin (`kasa_tipi_belirsiz`, `kasa_tipi_belirsiz_sebep`) mevcut downstream kodda (quality_gate, admin_panel, YukBurada payload dönüşümü) bir kırılmaya yol açmayacağı varsayılıyor — bu alanlar YukBurada'ya gönderilen payload'a DAHİL EDİLMEMELİ (sadece iç izleme amaçlı), plan adımında `submit_approved_loads.py`'nin payload dönüşümünde bu yeni alanların filtrelendiği teyit edilmeli.
- "İpucu yok" vs "kural eşleşmedi" ayrımı için basit bir sezgisel yöntem (mesajda bilinen kasa-tipi anahtar kelimelerinden biri geçiyor mu diye kontrol) kullanılacağı varsayılıyor — bu, `data/yuk_tipi.json`'daki TÜM pattern kelimelerinin bir listesini çıkarıp mesajda bunlardan biri var mı diye bakmak şeklinde olabilir; kesin algoritma plan adımında netleşecek.

## Unknowns
- `data/yuk_tipi.json`'ın gerçek içeriği/boyutu (plan adımında dosya okunarak teyit edilmeli).
- Panelde (`admin_panel.py`) "belirsiz kasa tipi" görünürlüğünün bu görevde mi yoksa ayrı bir görevde mi ekleneceği (bkz. Kapsam Dışı) — plan adımında kullanıcıyla netleştirilmeli.
- "İpucu var ama kural eşleşmedi" tespitinin kesin algoritması (bkz. Assumptions).

## Sorular ve Cevaplar (ham kayıt)
1. Persona → Panel operatörü (Haiku alt-ajanı tarafından yanıtlandı: son müşteri için fark etmek çok geç olur).
2. Ana hedef/neden → İkisi birden, önce görünürlük (Haiku alt-ajanı tarafından yanıtlandı: kural genişletme sürekli devam eden bir bakım görevi).
3. Happy path → Mevcut davranış korunur, değişmez (Haiku alt-ajanı tarafından yanıtlandı).
4. Edge case 1 (hiç ipucu yok) → Genel varsayılan KULLAN + "ipucu yok" flag'i (Haiku alt-ajanı tarafından yanıtlandı: ilan akışı kırılmamalı ama belirsizlik fark edilmeli).
5. Edge case 2 (ipucu var, kural eşleşmedi) → Flag + log gerekli (Haiku alt-ajanı tarafından yanıtlandı: hangi ifadelerin eklenmesi gerektiği görülebilsin).
6. Davranış sözleşmesi tablosu → yukarıdaki tabloya işlendi (Haiku alt-ajanı tarafından yanıtlandı, "hiçbir şey yapılamadı" satırı "ipucu yok" ile aynı olduğu için birleştirildi).
7. Başarı ölçütü/benchmark → görünürlük metriği + regresyon yok (Haiku alt-ajanı tarafından yanıtlandı).
8. Kapsam dışı → büyük kural genişletme, AI mimarisi değişikliği kapsam dışı (Haiku alt-ajanı tarafından yanıtlandı).
9. Bağımlılıklar → vehicle_type_matcher.py, text_gen_parser.py, yuk_tipi.json, admin_panel.py (opsiyonel) (Haiku alt-ajanı tarafından yanıtlandı).
10. Performans/güvenlik kısıtı → yok, minimal overhead (Haiku alt-ajanı tarafından yanıtlandı).
11. Rollback beklentisi → flag'ler sadece ek bilgi, mevcut davranışı değiştirmez (Haiku alt-ajanı tarafından yanıtlandı).
12. Kabul kriteri sahibi → kullanıcı + otomatik test birlikte (Haiku alt-ajanı tarafından yanıtlandı).
13. Test stratejisi oranı → 70/20/10 (Haiku alt-ajanı tarafından yanıtlandı).
14. Bilinen riskler/varsayımlar → yuk_tipi.json kapsamı taranmadı, plan adımında teyit edilmeli (Haiku alt-ajanı tarafından yanıtlandı).
