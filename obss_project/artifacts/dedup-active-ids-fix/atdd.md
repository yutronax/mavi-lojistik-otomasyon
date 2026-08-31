---
task_slug: dedup-active-ids-fix
jira_id: null
saga_task_id: null
priority: critical
coverage_target: 85
performance_target: null
memory_target: null
test_strategy:
  unit: 85
  integration: 15
  e2e: 0
affected_modules:
  - src/parsers/veri_cekici_ayristirici.py
---

# ATDD — dedup-active-ids-fix

## OLAY ÖZETİ — Bu görev neden var
Kullanıcı, DeepSeek/Groq bütçesinin çok hızlı tükenmesinin asıl nedeninin
"yetersiz model kotası" değil, **aynı mesajın gereksiz yere tekrar tekrar
işlenmesi** olabileceğini öne sürdü. VPS production loglarında bu doğrulandı:
`grep '\[JOB\] Islem BASLADI' logs/pm2_out.log` ile aynı mesaj ID'lerinin
**3 ila 6 kez** işlendiği görüldü (78.599 toplam "iş başladı" logu, tekil
mesaj sayısından belirgin şekilde fazla).

**Kök neden (kod okunarak doğrulandı):** `src/parsers/veri_cekici_ayristirici.py`:
- `_task_wrapper` (satır 249-274), bir mesaj işlendikten sonra `finally`
  bloğunda HER DURUMDA (başarı/hata fark etmeksizin) `msg_id`'yi
  `self.active_ids`'ten çıkarıyor (satır 261-263).
- `mark_id_handled()` ise SADECE `save_results()`'taki `has_valid_shipment`
  koşulu `True` ise çağrılıyor (satır 916-941). Bu koşul: `'error' in entry`
  VEYA `status == 'duplicate'` VEYA sevkiyatlardan birinde `nereden_il` YA
  DA `nereye_il` (SADECE İL alanları) dolu.
- Ama `process_message_task`'ın KENDİ filtresi (satır ~748-753) bir
  sevkiyatı `nereden_il OR nereden_ilce` (İL YA DA İLÇE) varsa geçerli
  sayıp `status: 'success'` ile döndürüyor.
- **Uyuşmazlık**: AI bir mesajdan sadece İLÇE çıkarıp İL alanını boş
  bırakırsa (`process_message_task` bunu geçerli/başarılı sayar), `save_results`
  bunu `has_valid_shipment=False` olarak değerlendirip `save_payload`'a
  HİÇ EKLEMEZ → `mark_id_handled` HİÇ ÇAĞRILMAZ → ama `active_ids`'ten
  zaten çıkarılmıştı (`_task_wrapper`'ın koşulsuz `finally` bloğu) → bir
  sonraki poll döngüsünde (WhatsApp API'nin "son 100 mesaj" penceresi
  aynı mesajı tekrar döndürdüğü sürece, her ~20-40 saniyede bir) mesaj
  TEKRAR kuyruğa girip AI'ye TEKRAR gönderiliyor — mesaj bu pencereden
  düşene kadar SÜREKLİ TEKRARLANAN bir AI çağrısı maliyeti oluşuyor.

## Persona
Sistem kendisi (arka plan WhatsApp mesaj işleme pipeline'ı).

## Hedef (Neden)
Her mesajın, sonucu ne olursa olsun (başarılı/hatalı/geçersiz konum/tekrar),
TAM OLARAK BİR KEZ AI'ye gönderilmesini garanti etmek — `active_ids`'ten
çıkarılma ile `mark_id_handled` çağrılması arasındaki senkronizasyon
kopukluğunu gidererek.

## User Story
As a sistem (mesaj işleme pipeline'ı)
I want her mesajın, işleme sonucundan bağımsız olarak, tam olarak bir kez
AI'ye gönderilmesini
So that gereksiz tekrar AI çağrıları yüzünden API bütçesi boşa harcanmasın.

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given bir mesaj AI tarafından işlenip `status: 'success'`
   döner AMA çıkarılan sevkiyat(lar)ın SADECE ilçe alanı dolu, il alanı
   boşsa (`nereden_ilce`/`nereye_ilce` dolu, `nereden_il`/`nereye_il` boş),
   When `save_results()` çalışır, Then bu sonuç YİNE DE `save_payload`'a
   eklenir ve `mark_id_handled()` çağrılır — `process_message_task`'ın
   "geçerli" saydığı HER sonuç, `save_results`'ın "kaydedilmeye değer"
   saydığı sonuçla TUTARLI olmalı (aynı il/ilçe kriteri).
2. [Critical] Given bir mesaj işlenirken herhangi bir nedenle (`status`
   ne olursa olsun) `process_message_task` bir sonuç döndürüyor, When
   `_task_wrapper`'ın `finally` bloğu `active_ids`'ten çıkarma işlemini
   yapıyor, Then bu ANCAK `mark_id_handled()` GERÇEKTEN çağrıldıktan
   SONRA (veya aynı anda, atomik olarak) gerçekleşmeli — `active_ids`'ten
   çıkarılıp `mark_id_handled` çağrılmayan bir ARA DURUM olmamalı.
3. [High] Given bir mesaj `process_message_task` içinde exception
   fırlatıyor (örn. AI API'si tamamen erişilemez), When `_task_wrapper`'ın
   `except` bloğu çalışıyor, Then bu mesaj YİNE DE `mark_id_handled()`
   ile işaretlenmeli (mevcut kodda SADECE loglanıp hiçbir kalıcı işaret
   BIRAKILMIYOR — bu da sonsuz tekrar riski taşıyor, düzeltilmeli).
4. [High] Given aynı mesaj ID'si zaten `active_ids` içindeyken (hâlâ
   işleniyor), When yeni bir poll döngüsü aynı mesajı tekrar buluyor,
   Then `add_to_processing_queue`'nun mevcut `active_ids` kontrolü
   (satır 495-497) bunu ATLAMALI — bu davranış ZATEN DOĞRU ÇALIŞIYOR,
   DEĞİŞTİRİLMEYECEK, sadece regresyon testiyle korunacak.
5. [Medium] Given bir mesaj gerçekten mükerrer (body hash zaten
   `active_body_hashes`'te), When `add_to_processing_queue` çalışıyor,
   Then bu mesaj kuyruğa HİÇ eklenmez — bu davranış ZATEN DOĞRU
   ÇALIŞIYOR, DEĞİŞTİRİLMEYECEK, sadece regresyon testiyle korunacak.
6. [Medium] Given düzeltme sonrası, When production loglarında (deploy
   sonrası, canlı gözlemle) aynı mesaj ID'sinin `[JOB] Islem BASLADI`
   log satırı sayılır, Then her ID en fazla 1 kez görünmeli (mevcut
   3-6 tekrar durumunun ortadan kalktığı canlı olarak doğrulanacak —
   bu, kod testiyle değil, deploy sonrası manuel log incelemesiyle
   teyit edilecek bir Benchmark kriteri).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | AC |
|---|---|---|---|---|
| 1 | Sadece ilçe dolu, il boş sevkiyat | `status: success` (DEĞİŞMEDİ) | `save_payload`'a eklenir, `mark_id_handled` çağrılır (YENİ) | AC-1 |
| 2 | Herhangi bir işlem sonucu | Mevcut dönüş değerleri DEĞİŞMEDİ | `active_ids` çıkarma, `mark_id_handled`'dan SONRA yapılır | AC-2 |
| 3 | `process_message_task` exception fırlatıyor | Loglanır (DEĞİŞMEDİ) | `mark_id_handled` çağrılır (YENİ — şu an çağrılmıyor) | AC-3 |
| 4 | Mesaj hâlâ aktif işleniyor | Kuyruğa eklenmez (DEĞİŞMEDİ) | Yok | AC-4 |
| 5 | Mesaj body'si mükerrer | Kuyruğa eklenmez (DEĞİŞMEDİ) | Yok | AC-5 |
| 6 | Canlı doğrulama | N/A (log gözlemi) | N/A | AC-6 |

Kısmi başarı: AC-1'de ele alındı — "kısmen geçerli" (sadece ilçe) bir
sonuç, `process_message_task`'ın kendi kriterine göre TAM başarı sayılıp
kalıcı olarak işaretlenmeli, "yarım kaydedilip tekrar denenecek" bir ara
durum OLMAMALI.
Hiçbir şey yapılamadı ama hata da yok: AC-3'te ele alındı — exception
durumunda bile mesaj kalıcı olarak işaretlenmeli (aksi halde "hiçbir şey
yapılamadı" durumu sessizce sonsuz tekrara dönüşüyor, bu YASAK).
Boş sonuç ↔ hata ayrımı: Bu görev kapsamında yeni bir ayrım gerekmiyor,
mevcut `status: 'success'`/`'error'` ayrımı korunuyor — sadece HANGİ
sonuçların "kalıcı olarak işaretlenmeye değer" sayıldığı tutarlı hale
getiriliyor.

## Test Strategy
Unit: 85% — `save_results()`'ın il/ilçe tutarlılığı, `_task_wrapper`'ın
exception durumunda da `mark_id_handled` çağırdığı, sıra garantisi
(active_ids çıkarma ancak mark_id_handled'dan sonra).
Integration: 15% — `add_to_processing_queue` → `_task_wrapper` →
`save_results` tam akışının, "sadece ilçe" senaryosunda mesajı GERÇEKTEN
kalıcı işaretlediğinin uçtan uca testi (mock AI yanıtıyla).
E2E: 0% — UI değişikliği yok.

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Diğer ölçülebilir kriterler: Deploy sonrası VPS loglarında (en az 24 saat
gözlemle) aynı mesaj ID'sinin `[JOB] Islem BASLADI` sayısı >1 olan kayıt
sayısı sıfıra inmeli (mevcut durumda onlarca tekrar var).

## Kapsam Dışı
- `add_to_processing_queue`'nun `active_ids`/`active_body_hashes`
  kontrolleri — ZATEN DOĞRU çalışıyor, dokunulmuyor.
- Groq/DeepSeek model seçimi/sırası — `deepseek-primary-balance-alert`
  görevinde ele alındı, bu görevin kapsamı dışında.
- WhatsApp API'nin "son 100 mesaj" penceresi davranışı — üçüncü taraf
  API kısıtı, değiştirilemez.
- Zaten var olan `is_body_known`/mükerrer-body kontrolü mantığı —
  değiştirilmiyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/parsers/veri_cekici_ayristirici.py` — `save_results()` (il/ilçe
  kriterini birleştirme), `_task_wrapper()` (sıra garantisi + exception
  durumunda da işaretleme).

## Rollback Beklentisi
Bu değişiklik SADECE "hangi sonuçların kalıcı işaretlendiği" kriterini
genişletiyor (daha fazla mesaj kalıcı işaretlenecek, daha AZ değil) — bu
yüzden geri alınması güvenlidir, eski davranışa (bazı mesajların hiç
işaretlenmemesi) dönmek riskli olan taraf, YENİ davranış değil.

## Risks
- `has_valid_shipment` kriterini genişletmek (il/ilçe ikisini de kabul
  etmek), önceden "geçersiz" sayılıp atlanan bazı sevkiyatların artık
  `save_payload`'a girmesine yol açabilir — ama bu zaten
  `process_message_task`'ın KENDİ tanımladığı geçerlilik kriteriyle
  TUTARLI hale getiriliyor, yeni bir gevşetme değil, mevcut bir
  tutarsızlığın giderilmesi.
- Exception durumunda `mark_id_handled` çağırmak, GERÇEKTEN geçici bir
  hata (ör. ağ kesintisi) durumunda mesajın bir daha HİÇ denenmemesine
  yol açabilir — ama mevcut kodun kendi yorumu ("Başarıdan bağımsız
  olarak... Böyle yapmazsak API hatasında sonsuz loop oluşur") zaten
  bu felsefeyi `save_results`'taki hata durumları için benimsemiş;
  bu görev sadece `_task_wrapper`'ın exception yolunu da AYNI felsefeyle
  tutarlı hale getiriyor.

## Assumptions
- `process_message_task`'ın "il VEYA ilçe" kriteri (satır ~748-753)
  DOĞRU kabul ediliyor — bu görev bunu DEĞİŞTİRMİYOR, sadece
  `save_results`'ı buna UYDURUYOR.

## Unknowns
- 78.599 toplam "iş başladı" logunun ne kadarının bu spesifik hatadan
  (il/ilçe uyuşmazlığı) kaynaklandığı, ne kadarının başka bir tekrar
  yolundan (henüz tespit edilmemiş) geldiği kesin olarak bilinmiyor —
  deploy sonrası canlı gözlemle (AC-6) netleşecek.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı hipotezi → "aynı mesajı tekrar mı işliyoruz, tasarrufsuz mu
   kullanıyoruz" (kullanıcı mesajından, birebir) — kod incelemesiyle
   DOĞRULANDI, kök neden bulundu.
2. Kök neden → `active_ids` (geçici) ile `mark_id_handled` (kalıcı)
   arasındaki senkronizasyon kopukluğu, spesifik olarak il/ilçe kriter
   uyuşmazlığı yüzünden (ben bulup doğruladım, gerçek production
   loglarıyla kanıtladım).
