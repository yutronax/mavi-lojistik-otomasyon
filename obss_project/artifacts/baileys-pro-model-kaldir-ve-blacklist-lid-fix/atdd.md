---
task_slug: baileys-pro-model-kaldir-ve-blacklist-lid-fix
jira_id: null
saga_task_id: 363
priority: high
coverage_target: 80
performance_target: null
memory_target: null
test_strategy:
  unit: 60
  integration: 30
  e2e: 10
affected_modules:
  - text_gen_parser.py
  - sidecar/bridge.js
---

# ATDD — baileys-pro-model-kaldir-ve-blacklist-lid-fix

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga #363 altında takip ediliyor.

## Persona
Sistem operatörü (kullanıcı) — hem AI maliyetlerini kontrol altında tutmak
hem de kara listeye aldığı numaraların gerçekten engellendiğinden emin
olmak istiyor.

## Hedef (Neden)
1. `deepseek-v4-pro` fallback modeli gereksiz maliyet yaratıyor
   (kullanıcı: "o çok yiyor") — kaldırılacak.
2. WhatsApp'ın LID (Linked ID) adresleme moduna geçmesiyle, Baileys
   kaynaklı mesajlarda gönderenin gerçek telefon numarası yerine LID
   görünüyor — kara liste bu LID ile eşleşmediği için engellenmiş
   numaralar hâlâ ilan atabiliyor (kullanıcı: "kara liste işlevsiz").

## User Story
As a sistem operatörü
I want (1) pahalı fallback modelin tamamen kaldırılmasını ve (2) kara
listenin LID yerine gerçek telefon numarasıyla çalışmasını
So that hem AI maliyetleri düşsün hem de engellediğim numaralar gerçekten
engellenmiş olsun

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `text_gen_parser.py`'nin model fallback zinciri, When
   `deepseek-v4-flash` (birincil model) başarısız olur, Then sıradaki
   deneme doğrudan Groq (`openai/gpt-oss-20b`) olmalı — `deepseek-v4-pro`
   zincirde HİÇ görünmemeli.
2. [Critical] Given `self.fallback_models` attribute'u, When kod okunur,
   Then boş liste (`[]`) olmalı — `deepseek-v4-pro` string'i kod tabanında
   (bu iki dosya kapsamında) hiçbir yerde geçmemeli.
3. [Critical] Given `sidecar/bridge.js`'in `toWhapiShape()` fonksiyonu bir
   grup mesajı işliyor ve `msg.key.participantAlt` alanı DOLU (gerçek
   telefon numarası), When mesaj dönüştürülür, Then hem `from` alanı hem
   de (dolaylı olarak) blacklist kontrolüne giden değer `participantAlt`
   olmalı, LID (`participant`) DEĞİL.
4. [High] Given `msg.key.participantAlt` alanı BOŞ/undefined (Baileys'in
   bu alanı her zaman sağlama garantisi yok), When mesaj dönüştürülür,
   Then mevcut davranışa (regresyon olmadan) geri dönülmeli — `from`
   alanı `participant` (LID) olarak dolmaya devam etmeli, mesaj İŞLENMEYE
   devam etmeli (reddedilmemeli).
5. [Medium] Given kara listeye gerçek bir telefon numarası eklenmiş VE
   gelen mesajın `participantAlt`'ı bu numarayla eşleşiyor, When
   `add_to_processing_queue()` çalışır, Then mesaj mevcut blacklist
   mantığıyla (`is_phone_in_list`) engellenmeli — bu, düzeltmenin gerçek
   kanıtı.
6. [Medium] Given `deepseek-v4-flash` VE Groq (`openai/gpt-oss-20b`) İKİSİ
   DE başarısız olur (pro artık yok), When bu durum oluşur, Then mevcut
   "tüm modeller tükendi" hata davranışı (retry/log, mevcut kod)
   DEĞİŞMEDEN korunmalı — bu bir regresyon testi.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: flash başarılı | Normal parse sonucu | Yok (model değişikliği şeffaf) | Değişiklik yok | AC-1 |
| 2 | participantAlt dolu, blacklist'te eşleşiyor | Mesaj engellenir (mevcut blacklist davranışı) | `mark_id_handled` çağrılır, mesaj kuyruğa girmez | Panelde hiç görünmez (mevcut davranış) | AC-3,5 |
| 3 | participantAlt YOK (undefined) | Mesaj `participant` (LID) ile işlenir | Blacklist kontrolü LID ile yapılır (muhtemelen eşleşmez — bilinen sınırlama) | Mesaj normal işlenir (regresyon yok) | AC-4 |
| 4 | flash + Groq ikisi de başarısız (pro yok) | Mevcut "tüm modeller tükendi" davranışı (koda dokunulmuyor) | Mevcut hata/log mekanizması | Mevcut davranış | AC-6 |
| 5 | flash 429/rate-limit | Groq'a geçer (pro'ya değil) | Mevcut key-rotation mantığı (satır ~559-565, bu görevde DOKUNULMUYOR) korunur | Mevcut davranış | AC-1 |
| 6 | Hiçbir şey yapılamadı ama hata yok: participantAlt YOK + blacklist LID ile eşleşmiyor | Mesaj normal işlenir (engellenmez) | Blacklist etkisiz kalmaya devam eder — bu AÇIK, BİLİNEN bir sınırlama | Engellenen numara hâlâ ilan atabilir (kısmi iyileştirme, tam çözüm değil) | AC-4 (sınırlama olarak belgelendi) |

Kısmi başarı: Bu görevde N/A — model seçimi ve alan okuma ikili (ya doğru
değer okunur ya fallback'e düşülür), ara bir "kısmi" durum yok.
Hiçbir şey yapılamadı ama hata da yok: Satır 6'da detaylandırıldı —
`participantAlt` yoksa blacklist LID ile hâlâ etkisiz kalabilir, bu
SESSİZCE kabul edilen, belgelenmiş bir sınırlama (Baileys'in garantisi
olmadığı için %100 çözüm mümkün değil).
Boş sonuç ↔ hata ayrımı: Bu görevde N/A — model/alan seçimi başarısız
olursa exception fırlamaz, sessizce fallback değerine döner (bu bilinçli
bir tasarım, "hata" değil "fallback").

Yetkisiz erişim, Zaman aşımı, Kaynak yok satırları bu görevde uygulanmıyor
— model seçimi ve alan okuma yerel/senkron işlemler, dış kaynak/yetki
kontrolü içermiyor (silindi).

## Test Strategy
Unit: 60% — `text_gen_parser.py`'nin `models_to_try` listesi (pro yok,
sıra doğru), `toWhapiShape()`'in participantAlt/participant seçim mantığı
Integration: 30% — `add_to_processing_queue()`'nun participantAlt ile
gelen bir mesajı gerçekten blacklist'e göre engellediğinin uçtan uca testi
E2E: 10% — VPS'e canlı erişim yok, bu oran gerçek bir e2e testine değil,
mevcut test suite'inin regresyonsuz geçmesine karşılık geliyor

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: yok
Memory: yok
Diğer ölçülebilir kriterler:
- `grep -rn "deepseek-v4-pro" text_gen_parser.py` → SIFIR sonuç
- participantAlt mevcut olan test mesajlarında blacklist eşleşme oranı:
  %100 (test edilebilir, kesin hedef)
- participantAlt YOK olan mesajlarda: mesaj yine de işlenir (reddedilmez) —
  regresyon testi

## Kapsam Dışı
- Baileys kütüphanesinin `participantAlt`'ı her zaman sağlayıp
  sağlamadığını upstream'de araştırmak/rapor açmak
- Admin panelin blacklist yönetim UI'ı (sadece backend mantığı değişiyor)
- Satır ~559-565'teki `if "gemini" in model_name:` dalının dead-code olup
  olmadığını araştırmak/temizlemek (ayrı bir görev olabilir)
- `participantAlt` yoksa blacklist'i LID bazlı çalıştıracak alternatif bir
  mekanizma (örn. LID→numara eşleme veritabanı) kurmak — bu görev sadece
  "varsa kullan" düzeltmesi yapıyor, "her zaman çalışsın" garantisi vermiyor

## Etkilenen Dosyalar/Modüller (bilinen)
- `text_gen_parser.py` (satır 73-77, 463 — fallback_models ve models_to_try)
- `sidecar/bridge.js` (satır 82, 95 — toWhapiShape())

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımı başlamadan önce `git rev-parse
--show-toplevel` ile kontrol edilecek.

## Rollback Beklentisi
Şema/migration değişikliği yok, düz kod değişikliği. Sorun çıkarsa `git
revert` yeterli.

## Risks
- `participantAlt` alanının Baileys'in her sürümünde/her mesaj tipinde
  garantili olmadığı — bu görev "varsa kullan" ile kısmi iyileştirme
  sağlıyor, blacklist'in %100 güvenilir olacağı garanti edilmiyor
  (kullanıcıya açıkça belirtilecek).
- Pro model kaldırıldıktan sonra flash+Groq ikisi de başarısız olan mesaj
  oranının artıp artmayacağı bilinmiyor (pro bir güvenlik ağıydı) — kabul
  edilebilir bir maliyet-güvenilirlik trade-off'u olarak kullanıcı
  tarafından zaten onaylandı.

## Assumptions
- `msg.key.participantAlt`'ın gerçek telefon numarası formatında
  (`<numara>@s.whatsapp.net`) geldiği, önceki bir pm2 log gözleminden
  varsayılıyor — VPS'e canlı erişim olmadığı için bu görevde tekrar
  doğrulanamadı.
- Blacklist'teki numaraların formatı `is_phone_in_list()`'in zaten
  normalize ettiği formatla uyumlu (bu fonksiyona dokunulmuyor).

## Unknowns
- `participantAlt`'ın Baileys'in TÜM mesaj tiplerinde (metin, medya,
  reaction vb.) tutarlı şekilde sağlanıp sağlanmadığı net değil — `plan`
  adımında Baileys tip tanımlarına (varsa `node_modules` içindeki .d.ts
  dosyaları) bakılarak netleştirilebilir.

## Sorular ve Cevaplar (ham kayıt)
1. Pro kaldırma sonrası fallback zinciri → `[model_robust] +
   ['openai/gpt-oss-20b']`, pro'suz (Haiku alt-ajanı tarafından
   yanıtlandı, kullanıcının "tamamen kaldır" talebiyle uyumlu)
2. `fallback_models` attribute'u → boş liste `[]` kalsın, CAVEMAN ile
   tutarlı esneklik (Haiku alt-ajanı tarafından yanıtlandı)
3. Satır ~559-565'teki "gemini" dalı → bu görevde dokunulmuyor, kapsam
   dışı bırakıldı (Haiku alt-ajanı tarafından yanıtlandı)
4. participantAlt garantisi yok → fallback: varsa kullan, yoksa mevcut
   LID davranışına dön (Haiku alt-ajanı tarafından yanıtlandı, regresyon
   önleme önceliği)
5. `from` alanının kendisi de participantAlt'a geçsin mi → EVET, tek
   kaynak tutarlılığı için (Haiku alt-ajanı tarafından yanıtlandı)
6. Test stratejisi oranı → 60/30/10 (Haiku alt-ajanı tarafından yanıtlandı)
7. Kapsam dışı → Baileys upstream araştırması, admin panel UI (Haiku
   alt-ajanı tarafından yanıtlandı, kullanıcı mesajından da destekleniyor)
8. Rollback → git revert yeterli (Haiku alt-ajanı tarafından yanıtlandı)
9. Benchmark → grep ile pro model sıfır sonuç + participantAlt'lı
   mesajlarda %100 blacklist eşleşmesi (Haiku alt-ajanı tarafından
   yanıtlandı, orkestratör tarafından netleştirildi)
10. Etkilenen dosyalar → sadece text_gen_parser.py ve sidecar/bridge.js
    (Haiku alt-ajanı tarafından yanıtlandı)
