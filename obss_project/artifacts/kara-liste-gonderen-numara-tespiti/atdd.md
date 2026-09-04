---
task_slug: kara-liste-gonderen-numara-tespiti
jira_id: null
saga_task_id: null
priority: critical
coverage_target: 85
performance_target: null
memory_target: null
test_strategy:
  unit: 70
  integration: 25
  e2e: 5
affected_modules:
  - src/services/data_service.py
  - src/services/mongo_service.py
  - src/parsers/veri_cekici_ayristirici.py
  - sidecar/bridge.js
  - src/utils/phone_utils.py
---

# ATDD — kara-liste-gonderen-numara-tespiti

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task'ı bu oturumda MCP bağlantısı
zaman aşımına uğradığı için açılamadı (`saga` MCP CONNECT_TIMEOUT) —
`saga_task_id: null` bırakıldı, sonraki adımda (plan/code-copilot) tekrar
denenmeli.

## Persona
Sistem operatörü (kullanıcı) — kara listeye eklediği numaraların WhatsApp
gruplarına attığı ilanların, hâlâ AI'ya gidip panelde göründüğünü fark etti.

## Hedef (Neden)
Daha önce bu konuda bir düzeltme yapılıp (task: `baileys-pro-model-kaldir-
ve-blacklist-lid-fix`, commit c767210) red-team onayından geçmiş ve
deploy edilmişti (Baileys `participantAlt || participant || from` mantığı).
Ama kullanıcı gerçek WhatsApp trafiğinde blacklist'in hâlâ işe yaramadığını
bildiriyor ("orda da red yedim"). Bu oturumdaki kod incelemesi, önceki
düzeltmenin dokunmadığı AYRI bir katmanda somut bir bug ortaya çıkardı:

**Bulunan bug:** [data_service.py:212-214](src/services/data_service.py:212)
ve [mongo_service.py:128-130](src/services/mongo_service.py:128) — AI
parse SONRASI, panele sunum aşamasındaki blacklist filtresi — numarayı şu
sırayla arıyor: `item.get('phone') or item.get('sender')`, yoksa
`item['message_info'].get('sender')`. Gerçek prod verisinde
(`data/onaylanmamis_ayristirilmis_log.json`, 500 kayıt) `message_info.sender`
alanı bir İSİM string'i (örn. `"Onur Özkan"`), telefon numarası DEĞİL.
Gerçek numara `message_info.sender_number` alanında duruyor (450/500
kayıtta dolu, örn. `"905015972489"`) ve bu iki fonksiyon o alanı hiç
okumuyor. Sonuç: `is_phone_in_list()` bir isim ile telefon listesini
karşılaştırıyor — sözdizimsel olarak asla eşleşemez, bu katmandaki
blacklist tamamen işlevsiz.

AI-ÖNCESİ katman ([veri_cekici_ayristirici.py:504-510](src/parsers/veri_cekici_ayristirici.py:504)
ve [:704-710](src/parsers/veri_cekici_ayristirici.py:704), `add_to_processing_queue`
içinde) `msg.get('from', '')` kullanıyor — Baileys tarafında
`participantAlt` fallback'i zaten var ([sidecar/bridge.js:82](sidecar/bridge.js:82)),
ama bu alan Baileys tarafından garanti edilmiyor; garanti edilmezse LID
(`participant`) kullanılıyor ve blacklist'teki gerçek numarayla eşleşmiyor.
Whapi.cloud webhook kanalının (`whapi_fetcher.py`) `from` alanının gerçek
numara mı LID-benzeri bir kimlik mi döndürdüğü bu oturumda doğrulanmadı.

## User Story
As a sistem operatörü
I want çekilen bir WhatsApp mesajının hangi numaradan/hesaptan geldiğinin
AI'ya gönderilmeden ÖNCE güvenilir şekilde tespit edilmesini VE bu tespitin
panel/veritabanı katmanındaki blacklist filtresine de doğru şekilde
ulaşmasını
So that kara listeye eklediğim numaralar gerçekten ve HER katmanda
engellensin, ilanları hiçbir şekilde panelde görünmesin/AI'ya gitmesin

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `data_service.py`'nin unprocessed/blacklist filtreleme
   fonksiyonu VE bir kaydın `message_info.sender_number` alanı kara
   listedeki bir numarayla eşleşiyor, When filtre çalışır, Then bu kayıt
   `sender_number` alanı üzerinden ENGELLENMELİ (şu an `message_info.sender`
   — isim — okunduğu için asla engellenmiyor; bu AC'nin somut kanıtı).
2. [Critical] Given `mongo_service.py`'nin aynı filtre fonksiyonu, When
   MongoDB'den okunan bir dokümanın `message_info.sender_number` alanı
   kara listedeki bir numarayla eşleşiyor, Then bu doküman ENGELLENMELİ
   (aynı bug, ikinci katman).
3. [Critical] Given `veri_cekici_ayristirici.py`'nin `add_to_processing_queue`
   fonksiyonu (AI parse'tan ÖNCEki katman) VE Baileys'ten gelen mesajda
   `msg.key.participantAlt` DOLU ve kara listede, When mesaj işlenir, Then
   mesaj AI'ya hiç gönderilmeden engellenmeli (mevcut davranış — regresyon
   testi, önceki görevden korunmalı).
4. [High] Given `participantAlt` YOK (undefined) VE gerçek gönderen `participant`
   (LID) alanında, When mesaj işlenir, Then mesaj mevcut davranışla
   (fail-open, işlenmeye devam) tutarlı kalmalı AMA "gönderen kimliği LID,
   blacklist eşleşmesi belirsiz" seviyesinde WARN loglanmalı — şu an bu log
   yok, sessizce geçiyor.
5. [High] Given hiçbir katmanda (participantAlt, participant, from,
   sender_number) gönderen numarası tespit edilemiyor, When mesaj işlenir,
   Then mesaj yine fail-open işlenmeli (toptan bloklama YAPILMAMALI — iş
   kaybı riski) ama WARN/ERROR seviyesinde açıkça loglanmalı (şu an sessiz).
6. [Medium] Given `message_info.sender_number` alanının kaynağı (mesaj
   gövdesinden regex ile çıkarılan ilan telefonu mu, yoksa gerçek WhatsApp
   gönderen kimliği mi), When `plan` adımında bu netleştirilir, Then eğer
   bu alan gövdeden geliyorsa blacklist kontrolünde KULLANILMAMALI (ilan
   sahibinin numarası ile gönderen hesabın numarası farklı kişiler
   olabilir) — bu AC, `plan` adımında yapılacak kod okumasıyla
   kesinleştirilecek bir doğrulama şartı.
7. [Medium] Given kara listedeki bir numara farklı yazım formatlarında
   (0XXX, 90XXX, +90XXX) saklanıyor, When karşılaştırma yapılır, Then
   `is_phone_in_list()`'in mevcut normalizasyonu (`get_phone_variants`)
   her iki tarafta da tutarlı çalışmalı — regresyon testi.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: kara listedeki numaradan mesaj, sender_number/participantAlt ile eşleşiyor | Mesaj filtrelenir (continue/skip) | Log: `[BLOCK] ... from <numara>` | Panelde hiç görünmez | AC-1,2,3 |
| 2 | Girdi geçersiz/eksik: numara formatı bozuk (boşluklu, +'lı) | Normalize edilip tekrar karşılaştırılır | Yok | Doğru şekilde engellenir/geçer (regresyon yok) | AC-7 |
| 3 | Kaynak yok: participantAlt VE participant VE sender_number hiçbiri yok | Mesaj fail-open işlenir | **WARN log eklenir** (şu an yok) | Panelde normal görünür, ama loglarda iz bırakır | AC-5 |
| 4 | Kısmi başarı: participantAlt yok, sadece LID (participant) var | Mesaj fail-open işlenir, blacklist LID ile denenir (muhtemelen eşleşmez) | **WARN log: "LID kullanıldı, eşleşme belirsiz"** (şu an yok) | Panelde normal görünür | AC-4 |
| 5 | Hiçbir şey yapılamadı ama hata yok: numara hiç tespit edilemedi | Sessiz "başarı" DEĞİL — WARN loglanır, mesaj fail-open devam eder | Log kaydı | Kullanıcı loglara bakarsa görür, panelde fark etmez | AC-5 |
| 6 | Dış bağımlılık hatası (Whapi/Baileys API) | Bu görevin kapsamı dışı — mevcut hata yönetimi korunur | Değişmiyor | Değişmiyor | N/A |

Kaynak yok / Yetkisiz erişim / Zaman aşımı: Bu görev senkron, yerel alan
karşılaştırma mantığı değiştiriyor; ağ çağrısı veya yetkilendirme katmanı
içermiyor — "Yetkisiz erişim" ve "Zaman aşımı" satırları silindi (blacklist
bir yetkilendirme mekanizması değil, içerik filtresi).

Boş sonuç ↔ hata ayrımı: "Mesaj blacklist'te değil" (boş sonuç, normal
akış) ile "gönderen numarası hiç tespit edilemedi" (belirsizlik) AYNI
davranışı (fail-open, mesaj geçer) üretir AMA farklı log seviyesinde
ayrışmalı — birincisi log üretmez, ikincisi WARN üretir. Bu ayrım şu an
kodda YOK, bu görevin bir parçası.

## Test Strategy
Unit: 70% — `data_service.py`/`mongo_service.py`'nin blacklist alan seçim
sırası (sender_number öncelikli), `is_phone_in_list()` normalizasyon
regresyonu, Baileys `senderJid` fallback zinciri (participantAlt/participant/from)
Integration: 25% — AI-öncesi (`add_to_processing_queue`) VE AI-sonrası
(`data_service`/`mongo_service`) katmanların AYNI test numarasıyla tutarlı
şekilde engellediğinin uçtan uca doğrulanması
E2E: 5% — gerçek Baileys/Whapi bağlantısı bu ortamda yok; kullanıcı ayrıca
prod'da manuel doğrulama yapacak (daha önce bir kez "red yedim" dediği için)

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: yok (mantık/veri alanı düzeltmesi, performans kritik değil)
Memory: yok
Diğer ölçülebilir kriterler:
- Blacklist'e eklenmiş bir test numarasından simüle edilen mesaj, HEM
  `add_to_processing_queue` HEM `data_service.py` HEM `mongo_service.py`
  katmanında engellenmeli (3 katman da aynı sonucu vermeli) — şu an sadece
  1. katman çalışıyor, hedef 3/3.
- `grep "message_info'].get('sender')" src/services/` → blacklist
  bağlamında SIFIR sonuç (düzeltmeden sonra `sender_number` kullanılmalı).

## Kapsam Dışı
- Whapi.cloud webhook'unun `from` alanının LID mi gerçek numara mı
  döndürdüğünü upstream'de araştırmak (ayrı keşif görevi olabilir).
- Admin panelin blacklist yönetim UI'ı.
- Baileys sidecar'ının JID çözümleme mantığının (`participantAlt` fallback,
  commit c767210) yeniden yazılması — mevcut mantık korunacak, sadece
  AI-sonrası katmandaki bug'a odaklanılacak.
- `message_info.sender_number`'ın kaynağının (gövdeden regex mi, gerçek
  JID mi) upstream'de (parser tarafında) değiştirilmesi — bu görev sadece
  MEVCUT alanların blacklist'te DOĞRU kullanılmasını sağlıyor; alanın
  kendisinin nereden geldiği `plan` adımında netleştirilecek ama kaynağı
  değiştirmek ayrı bir görev olabilir (AC-6'ya bağlı).

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/services/data_service.py` (satır ~210-219 — blacklist filtre bug'ı)
- `src/services/mongo_service.py` (satır ~127-136 — aynı bug)
- `src/parsers/veri_cekici_ayristirici.py` (satır ~504-510, ~704-710 —
  AI-öncesi katman, regresyon testi kapsamında)
- `sidecar/bridge.js` (satır 82 — mevcut participantAlt fallback, regresyon)
- `src/utils/phone_utils.py` (`is_phone_in_list`, dokunulmayacak ama test
  edilecek)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımı başlamadan önce `git rev-parse --show-toplevel`
ile kontrol edilecek. Bu oturumda tüm aramalar zaten proje klasörü
(`maviLojistik` worktree) içinde kaldı.

## Rollback Beklentisi
Şema/migration değişikliği yok, düz kod değişikliği (alan seçim sırası +
log ekleme). Sorun çıkarsa `git revert` yeterli.

## Risks
- `message_info.sender_number`'ın gerçekten gövdeden regex mi yoksa gönderen
  JID'i mi olduğu netleşmeden düzeltme yapılırsa, bug'ı gizlice başka bir
  yanlış alana taşıma riski var — `plan` adımında MUTLAKA doğrulanmalı
  (parser kodunda bu alanın nasıl dolduğuna bakılarak).
- Whapi kanalının `from` alanının LID-benzeri bir davranışı olup olmadığı
  bilinmiyor — sadece Baileys kanalı için önceki görevde bir düzeltme
  yapılmıştı, Whapi kanalı hiç incelenmedi.
- Blacklist numaralarının farklı katmanlarda farklı normalizasyon formatında
  saklanma ihtimali (regresyon riski, AC-7 ile test ediliyor).

## Assumptions
- Baileys `participantAlt || participant || from` fallback zincirinin
  kendisinin doğru çalıştığı varsayılıyor (önceki red-team onayı) — sorun
  bu zincirde değil, AI-sonrası katmanda.
- Kullanıcının "orda da red yedim" ifadesi, önceki düzeltmenin production'da
  yetersiz kaldığını doğruluyor ama HANGİ katmanda başarısız olduğunu
  belirtmiyor — bu ATDD, kod incelemesiyle bulunan somut bug'a (AI-sonrası
  katman) odaklanıyor; AI-öncesi katmanda da ayrı bir sorun çıkarsa `plan`
  adımında ek AC eklenmeli.

## Unknowns
- `message_info.sender_number` alanının gerçek kaynağı (gövde regex mi,
  gönderen JID mi) — `plan` adımında ilgili parser koduna (muhtemelen
  `production_parser.py` veya `text_gen_parser.py`) bakılarak netleştirilmeli.
- Whapi.cloud webhook payload'unun gönderen alanı formatı.

## Sorular ve Cevaplar (ham kayıt)
1. Happy path/güven sırası → Whapi: `from` (doğrulanmamış varsayım, gerçek
   numara döndürdüğü varsayılıyor); Baileys: mevcut `participantAlt >
   participant > from` sırası korunuyor (Sonnet 5 alt-ajanı tarafından
   yanıtlandı)
2. Edge case'ler → (a) participantAlt yoksa LID ile fail-open devam,
   (b) Whapi formatı kapsam dışı, (c) gövdedeki ilan numarası gönderen
   kimliğiyle karıştırılmamalı (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Davranış sözleşmesi → numara tespit edilemezse fail-open + WARN log;
   AI-sonrası bug için sadece sender_number eklemek yetmez, alanın kaynağı
   netleştirilmeli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. Başarı ölçütü → 3 katmanın (add_to_processing_queue, data_service,
   mongo_service) aynı test numarasıyla tutarlı engellemesi (Sonnet 5
   alt-ajanı tarafından yanıtlandı)
5. Kapsam dışı → Whapi LID araştırması, admin panel UI, Baileys fallback
   yeniden yazımı, sender_number kaynağını değiştirmek (Sonnet 5 alt-ajanı
   tarafından yanıtlandı)
6. Bağımlılıklar → yukarıda listelenenler dışında yok (Sonnet 5 alt-ajanı
   tarafından yanıtlandı)
7. Performans/güvenlik kısıtı → yok, mantık düzeltmesi (Sonnet 5 alt-ajanı
   tarafından yanıtlandı)
8. Rollback → git revert yeterli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Kabul kriteri → kullanıcı + otomatik test, kullanıcı ayrıca prod'da
   manuel doğrulayacak (Sonnet 5 alt-ajanı tarafından yanıtlandı)
10. Test stratejisi → 70/25/5 unit/integration/e2e, alan eşleştirme
    mantığı hatası olduğu için unit ağırlıklı (Sonnet 5 alt-ajanı
    tarafından yanıtlandı)
11. Riskler/Unknown'lar → sender_number kaynağı belirsizliği, Whapi format
    belirsizliği, normalizasyon tutarlılığı riski (Sonnet 5 alt-ajanı
    tarafından yanıtlandı)
12. Persona/Hedef → kullanıcı mesajından + bu oturumdaki kod incelemesinden
    (kullanıcı mesajından + kod incelemesinden, tekrar sorulmadı)
