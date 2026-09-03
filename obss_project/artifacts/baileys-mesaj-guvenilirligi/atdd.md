---
task_slug: baileys-mesaj-guvenilirligi
jira_id: null
saga_task_id: 361
priority: high
coverage_target: 80
performance_target: null
memory_target: "<50MB ek (thread-local Gemini client overhead)"
test_strategy:
  unit: 55
  integration: 35
  e2e: 10
affected_modules:
  - sidecar/bridge.js
  - src/api/webhook_server.py
  - src/utils/gemini_client.py
  - src/parsers/veri_cekici_ayristirici.py
---

# ATDD — baileys-mesaj-guvenilirligi

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga #361 altında takip ediliyor.

## Persona
Sistem operatörü (kullanıcı) — VPS'teki üretim pipeline'ının WhatsApp'tan
mesaj çekip Gemini ile ayrıştırdığını ve admin panelde sonuç olarak
gördüğünü bekliyor.

## Hedef (Neden)
Kullanıcı canlı pm2 loglarını paylaştı: bridge.js webhook'a mesaj POST
ediyor ("[WEBHOOK OK]"), ama admin panelde/onaylanmamış listede işlenmiş
sonuç görünmüyor. Kod incelemesiyle üç ayrı, birbirini besleyen kök neden
bulundu — bu görev üçünü birlikte gidererek "veri çekiliyor ama
işlenmiyor" şikayetini gerçekten kapatmayı hedefliyor.

## User Story
As a sistem operatörü
I want WhatsApp'tan gelen her mesajın ya başarıyla işlenmesini ya da NEDEN
işlenmediğinin açıkça loglanmasını, ve Gemini çağrılarının thread'ler
arası çakışmadan güvenilir çalışmasını
So that mesajların "veri geldi ama sonuç yok" şeklinde sessizce
kaybolmadığından emin olabileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `sidecar/bridge.js`'in `makeWASocket()` çağrısı, When
   soket başlatılır, Then `getMessage` callback'i tanımlı olmalı ve son
   ~200 gönderilen/alınan mesajı `msg.key.id` → mesaj eşlemesiyle tutan
   in-memory bir Map'ten okumalı (Baileys retry istediğinde boş dönmek
   yerine).
2. [Critical] **[DÜZELTİLDİ — plan adımında bulundu]** Given
   `text_gen_parser.py`'deki `TextGenParser.parse_async()` her model
   denemesinde (`_get_deepseek_client()`/`_get_async_client()`/
   `_get_gemini_client()`) TAZE bir async client (`AsyncOpenAI`/
   `AsyncGroq`/`google_genai.Client`) oluşturuyor ve API çağrısından sonra
   HİÇBİR ZAMAN kapatmıyor (`await client.close()` yok, `async with`
   kullanılmıyor), When bu client'lar GC tarafından sonradan (çoğunlukla
   farklı/kapanmış bir `asyncio.run()` event loop'unda) finalize edilmeye
   çalışılır, Then bu artık "Event loop is closed" hatasına yol AÇMAMALI —
   her client kullanımından hemen sonra (başarı veya hata fark etmeksizin)
   `await client.close()` çağrılmalı (`try/finally` veya `async with`).
   NOT: İlk turda önerilen `src/utils/gemini_client.py` +
   `threading.local()` yaklaşımı YANLIŞ dosyayı hedefliyordu — o dosya
   sadece GUI'de kullanılıyor (`src/gui/tanidk_yerler_panel.py`,
   `src/gui/yonetim_merkezi.py`), VPS mesaj işleme yolunda HİÇ devrede
   değil. Gerçek hedef `text_gen_parser.py`.
3. [Critical] **[DÜZELTİLDİ]** Given eşzamanlı 5+ worker thread'i (her biri
   kendi `asyncio.run()` çağrısıyla) gerçek (veya mock) AI çağrısı yapıyor,
   When bu senaryo testte simüle edilir, Then "RuntimeError: Event loop is
   closed" hatası oluşmamalı (kapatma garantisi test edilir — thread-local
   cache DEĞİL, per-call `close()` garantisi).
4. [High] Given `_handle_baileys_event()` bir mesajı kayıtlı grup listesi
   dışında olduğu için atladığında, When bu olur, Then mevcut
   `logger.debug`/`logger.warning` seviyesi INFO/WARNING'e çıkarılmalı ve
   atlanan mesaj sayısı + örnek chat_id log satırında görünür olmalı
   (mevcut satır 84-86 zaten log atıyor ama seviyesi `debug` — üretimde
   varsayılan log seviyesinde görünmüyor).
5. [High] Given Baileys bir grup mesajını decrypt edemediği (`messages.upsert`
   asla tetiklenmediği) durum, When bu olduğunda, Then bu görev
   `bridge_unhandled_messages.log`'a BENZER şekilde `risk_events.log`'a
   (mevcut `logRiskEvent` mekanizması) bir `decrypt_failed` olayı
   eklemeli — Baileys'in kendi `connection.update`/hata event'lerinden
   yakalanabildiği ölçüde (bkz. Unknowns — Baileys'in decrypt hatasını
   hangi event'te expose ettiği doğrulanmadı).
6. [Medium] Given `process_message_task` bir mesajı işlerken exception
   fırlatır (örn. Gemini hatası), When bu olur, Then mevcut davranış
   korunmalı: `_task_wrapper`'daki `except` bloğu `mark_id_handled`
   çağırıp mesajı "denendi ama başarısız" olarak işaretlemeli (var olan
   davranış, bu görevde BOZULMAMALI — regresyon testiyle korunacak).
7. [Medium] Given thread-local `GeminiClient` her thread için ayrı bir
   `genai.Client`/httpx bağlantı havuzu açar, When bu VPS'in kısıtlı
   (2GB RAM) ortamında çalışır, Then toplam ek bellek kullanımı
   `MAX_WORKERS_DEFAULT` sayısına göre sınırlı kalmalı (test:
   `MAX_WORKERS_DEFAULT` değeri koddan okunup makul olduğu doğrulanacak,
   yeni bir worker limiti EKLENMEYECEK — mevcut sınır zaten var).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: kayıtlı grup, decrypt OK, Gemini OK | Webhook HTTP 200 (mevcut, DEĞİŞMİYOR — fire-and-forget mimarisi korunuyor) | `save_results()` çağrılır, `onaylanmamis_ayristirilmis.json`'a (PROCESSED_FILE) satır eklenir | Admin panelde "onaylanmamış" listede yeni kayıt görünür | AC-2,3,6 |
| 2 | Girdi geçersiz (body boş / mid yok) | Webhook HTTP 200 (mevcut) | `add_to_processing_queue` içinde sessizce atlanır (mevcut davranış — bu görev DEĞİŞTİRMİYOR) | Hiçbir şey (mevcut `logger.debug` zaten var) | — (kapsam dışı, mevcut davranış korunuyor) |
| 3 | Kaynak yok: chat_id kayıtlı grup değil | Webhook HTTP 200 (mevcut) | Mesaj `_handle_baileys_event`'te filtrelenir, kuyruğa hiç girmez | **YENİ:** pm2 loglarında görünür seviyede (INFO/WARNING) "N mesaj kayıtlı olmayan gruptan atlandı" satırı | AC-4 |
| 4 | Yetkisiz erişim | N/A — SİLİNDİ | Webhook'ta auth/imza doğrulaması bu görevin kapsamı dışı; mevcut sistemde zaten yok, eklemek ayrı bir güvenlik kararı gerektirir | — | — |
| 5 | Dış bağımlılık hatası (Gemini API hatası, "Event loop is closed") | Webhook HTTP 200 (mevcut, POST zaten async) | **DÜZELTME:** thread-local client ile "Event loop is closed" oluşmamalı; gerçek Gemini API hatası olursa mevcut `except Exception` `{'status':'error', ...}` döner, `mark_id_handled` çağrılır (mevcut davranış korunur) | Mesaj "işlenemedi" olarak işaretlenir, tekrar denenmez (mevcut davranış — bu görevde retry mekanizması EKLENMİYOR) | AC-2,3 |
| 6 | Zaman aşımı (Gemini çağrısı çok uzun sürer) | Kapsam dışı — bu görevde timeout mekanizması eklenmiyor, mevcut google-genai SDK varsayılan timeout'u kullanılıyor | — | — | — (Unknowns'a not düşüldü) |
| 7 | Kısmi başarı (bazı shipment'lar valid, bazıları invalid_location) | Webhook HTTP 200 (mevcut) | Mevcut davranış korunur: `invalid_location=True` işaretiyle KAYDEDİLİR (silinmez), `has_invalid_location` flag'i set edilir | Panelde "uluslararası/bilinmeyen konum" etiketiyle görünür (mevcut davranış, bu görev DOKUNMUYOR) | — (regresyon koruması) |
| 8 | Hiçbir şey yapılamadı ama hata da yok (decrypt hatası VEYA sessiz webhook düşmesi) | Webhook HTTP 200 (mevcut) / Baileys tarafında hiç webhook'a gelmez | **DÜZELTME (AC-4, AC-5):** artık `risk_events.log`'a veya pm2 stdout'una görünür bir kayıt düşer — tamamen sessiz kalmaz | pm2 loglarında "decrypt_failed" veya "atlandı" satırı görülebilir | AC-4,5 |

Kısmi başarı: Satır 7'de detaylandırıldı — mevcut davranış (kaydet + flag'le) korunuyor, bu görev bunu bozmuyor.
Hiçbir şey yapılamadı ama hata da yok: Satır 8'de detaylandırıldı — bu görevin asıl amacı bu durumu SESSİZ olmaktan ÇIKARMAK (loglanabilir hale getirmek), tamamen ortadan kaldırmak değil (decrypt hatası kütüphane seviyesinde tam çözülemiyor, bkz. Risks).
Boş sonuç ↔ hata ayrımı: Webhook her zaman 200 döndüğü için (bilinçli fire-and-forget tasarım, bridge.js timeout'unu önlemek için) HTTP seviyesinde ayrım YOK — ayrım pm2 log satırlarında yapılıyor (bu görevin AC-4/AC-5'i tam olarak bunu sağlıyor).

Satır 4 (Yetkisiz erişim) ve Satır 6 (Zaman aşımı) silindi/kapsam dışı bırakıldı — yukarıda gerekçeleriyle birlikte.

## Test Strategy
Unit: 55% — `threading.local()` ile thread-başına client izolasyonu (her thread farklı instance alıyor mu), `getMessage` Map'inin LRU/boyut sınırı, `add_to_processing_queue`'nun regresyon davranışı (body/id kontrolü bozulmadı)
Integration: 35% — ThreadPoolExecutor üzerinden gerçek eşzamanlı çağrı simülasyonu (mock Gemini client ile "Event loop is closed" oluşmadığını kanıtlama), webhook_server.py'nin filtrelenen mesaj için log satırı ürettiğinin doğrulanması
E2E: 10% — mevcut `verify` skill'inin canlı tarayıcı/panel testiyle sınırlı (asıl E2E burada VPS'te pm2 log gözlemi olacak, bu `verify` adımında not düşülecek)

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: yok (bu bir güvenilirlik/doğruluk görevi, hız hedefi yok)
Memory: thread başına ek Gemini client overhead'i `MAX_WORKERS_DEFAULT` ile sınırlı kalmalı, yeni bir worker limiti eklenmez
Diğer ölçülebilir kriterler:
- Eşzamanlı thread testinde "Event loop is closed" hatası: 0 (test edilebilir, kesin hedef)
- Decrypt kayıp oranı: kütüphane seviyesi sınırlama nedeniyle SAYISAL hedef YOK — sadece "getMessage eklendi" doğrulanır, gerçek kayıp oranı VPS'te sonradan gözlemlenmeli (Unknowns)

## Kapsam Dışı
- Baileys kütüphanesinin kendisini fork'lamak veya patch'lemek (upstream sorun, WhiskeySockets/Baileys #886/#360/#2342)
- Admin panel UI değişiklikleri (örn. "Failed/Skipped Messages" sayaç kartı) — ayrı bir görev olabilir
- Webhook'a authentication/imza doğrulaması eklemek
- Gemini çağrıları için retry/backoff mekanizması eklemek (mevcut "başarısız olursa mark_id_handled ile bırak" davranışı korunuyor)
- Webhook `do_POST`'un HTTP durum kodu davranışını değiştirmek (200-önce-işle-sonra mimarisi korunuyor — bunu değiştirmek bridge.js'in timeout beklentisini de değiştirir, kapsamı büyütür)
- Timeout mekanizması eklemek (Satır 6, Davranış Sözleşmesi)

## Etkilenen Dosyalar/Modüller (bilinen)
**[DÜZELTİLDİ — plan adımında bulundu, gerçek kod yoluyla doğrulandı]**
- `sidecar/bridge.js` — `getMessage` callback + mesaj geçmişi Map'i
- `src/api/webhook_server.py` — log seviyesi düzeltmesi (`debug` → `info`/`warning`)
- `text_gen_parser.py` (kök dizin, `src/` altında DEĞİL) — `_get_deepseek_client()`,
  `_get_async_client()` (Groq), `_get_gemini_client()`'in döndürdüğü async
  client'ların kullanımdan sonra `await client.close()` ile kapatılması
  (`parse_async`, `_extract_locations_stage1_async`,
  `_resolve_neighborhood_async` içindeki tüm çağrı noktaları)
- ~~`src/utils/gemini_client.py`~~ — YANLIŞ HEDEF, kapsam dışına alındı:
  bu dosya sadece GUI'de (`tanidk_yerler_panel.py`, `yonetim_merkezi.py`)
  kullanılıyor, VPS mesaj işleme yolunda hiç devrede değil
- ~~`src/parsers/veri_cekici_ayristirici.py`~~ — thread-local değişikliği
  gerekmiyor (kapsam dışına alındı); `MAX_WORKERS_DEFAULT = 50` olduğu
  doğrulandı (satır 122) — bu değer değiştirilmiyor, sadece not düşülüyor
- `src/utils/gemini_adapter.py` — kontrol edildi: Gemini ile İLGİSİZ, aslında
  bir Ollama proxy'si (yanıltıcı isim). Kapsam dışı.

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — önceki görevlerde bu konuda net bilgi yok, `plan` adımı
başlamadan önce `git rev-parse --show-toplevel` ile kontrol edilecek.

## Rollback Beklentisi
Şema/migration değişikliği yok, düz kod değişikliği (callback ekleme,
thread-local factory, log seviyesi). Sorun çıkarsa `git revert` +
`pm2 restart` yeterli.

## Risks
- Baileys'in decrypt hatasını hangi event'te expose ettiği koda bakmadan
  netleşmedi (bkz. Unknowns) — AC-5'in tam olarak nasıl yakalanacağı
  `plan` adımında netleşmeli, mümkün olmazsa bu AC daraltılabilir.
- `getMessage` eklemek decrypt kaybını azaltabilir ama LID/Signal session
  senkronizasyon sınırlaması kütüphane seviyesinde olduğu için garantili
  %0 kayıp sağlamaz — bu net olarak kullanıcıya iletildi (önceki turda).
- Thread-local Gemini client, `veri_cekici_ayristirici.py`'nin `base_parser`
  gibi paylaşılan diğer bileşenlerini etkilemez mi, plan adımında
  doğrulanmalı (base_parser Gemini client'ı sarmalıyor mu yoksa ayrı mı).

## Assumptions
- VPS'e bu oturumdan (worktree sandbox) doğrudan erişilemiyor; kullanıcının
  paylaştığı pm2 log alıntıları gerçek üretim durumunu yansıtıyor kabul
  edildi.
- `MAX_WORKERS_DEFAULT` değerinin makul (VPS'in 2GB RAM'ine uygun) olduğu
  varsayıldı — plan adımında gerçek değer okunup teyit edilecek.
- Haiku alt-ajanının önerdiği HTTP durum kodları (400/500/504/202) gerçek
  koddaki (`webhook_server.py:110-114`) "her zaman 200, işlemeden önce"
  mimarisiyle ÇELIŞTIĞI için REDDEDİLDİ ve bu atdd.md'de mevcut mimariye
  sadık kalınarak düzeltildi — bu, Davranış Sözleşmesi tablosunda görülüyor.

## Unknowns
- Baileys'in decrypt hatasını (`GroupCipher.decrypt` içindeki
  "No session found") hangi event/hook üzerinden bridge.js'e expose
  ettiği net değil — `sock.ev.on('connection.update', ...)` içinde mi,
  yoksa ayrı bir logger/error event'i mi olduğu `plan` adımında Baileys
  kaynak koduna bakılarak netleştirilecek. AC-5 bu netleşmeye bağlı.
- `gemini_adapter.py`'nin `gemini_client.py`'deki client'ı mı sardığı,
  yoksa ayrı bir `genai.Client` mi oluşturduğu doğrulanmadı.

## Sorular ve Cevaplar (ham kayıt)
1. Kapsam (gözlemlenebilirlik mi, düzeltme mi) → (b) tam düzeltme (Haiku alt-ajanı tarafından yanıtlandı: kullanıcı "bitir" dedi)
2. getMessage kaynağı → in-memory Map, son ~200 mesaj (Haiku alt-ajanı tarafından yanıtlandı: oturum içi retry yeterli, disk gerekmiyor)
3. Gemini thread-safety yaklaşımı → threading.local() (Haiku alt-ajanı tarafından yanıtlandı: en az invaziv, lock'a göre performans/deadlock riski daha düşük)
4. Sessiz webhook düşmesi için UI mı log mu → sadece log seviyesi düzeltmesi, UI kapsam dışı (Haiku alt-ajanı tarafından yanıtlandı, orkestratör tarafından teyit edildi)
5. Benchmark → "Event loop is closed" = 0 (test edilebilir), decrypt için sayısal hedef yok (Haiku alt-ajanı tarafından yanıtlandı, orkestratör tarafından teyit edildi)
6. Test stratejisi oranı → 55/35/10 (Haiku'nun 40/45/15 önerisi orkestratör tarafından bu projenin mevcut testlerinde e2e payının düşük tutulduğu gözlemine göre 55/35/10'a ayarlandı)
7. Kapsam dışı → Baileys fork/patch, admin panel UI (Haiku alt-ajanı tarafından yanıtlandı, kullanıcı mesajından da destekleniyor — sadece "bitir" dedi, UI istemedi)
8. Rollback → git revert yeterli (Haiku alt-ajanı tarafından yanıtlandı: schema/migration yok)
9. Etkilenen dosyalar → bridge.js, webhook_server.py, gemini_client.py, veri_cekici_ayristirici.py + gemini_adapter.py kontrol edilecek (Haiku'nun "kodu görmeden varsayım" notu Unknowns'a taşındı, orkestratör tarafından netleştirildi)
10. Performans/güvenlik kısıtı → thread-local overhead kabul edilebilir (Haiku alt-ajanı tarafından yanıtlandı: ~20MB max senaryo, VPS 2GB RAM'e göre kabul edilebilir)
11. (orkestratör düzeltmesi) HTTP durum kodları → Haiku'nun önerdiği 400/500/504/202 kodları gerçek `webhook_server.py` mimarisiyle (her zaman 200, async işleme) çelişiyordu, REDDEDİLDİ — Davranış Sözleşmesi tablosu gerçek koda sadık kalınarak yeniden yazıldı (kullanıcı mesajından/kod analizinden, alt-ajana tekrar sorulmadı)
