---
task_slug: baileys-webhook-bridge-uctan-uca-test
jira_id: null
saga_task_id: 350
priority: high
coverage_target: null
performance_target: null
memory_target: null
test_strategy:
  unit: 0
  integration: 30
  e2e: 70
affected_modules:
  - sidecar/bridge.js
  - src/api/webhook_server.py
  - src/parsers/veri_cekici_ayristirici.py (add_to_processing_queue)
---

# ATDD — baileys-webhook-bridge-uctan-uca-test

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #350 (epic #43 "Baileys — Webhook köprüsü", proje #8 "maviLojistik").

## Persona
Proje sahibi — Whapi.cloud'dan ($35/ay) Baileys'e (ücretsiz) geçiş projesinin üretime hazır olduğunu doğrulamak istiyor.

## Hedef (Neden)
`sidecar/bridge.js` → `webhook_server.py` (`/baileys-webhook`) → `orchestrator.add_to_processing_queue()` zincirinin **gerçek bir WhatsApp mesajıyla** uçtan uca çalıştığını kanıtlamak. Şimdiye kadar sadece mock orchestrator ile test edildi (Saga #350 yorumları) — gerçek Baileys bağlantısı üzerinden gelen bir mesajla hiç doğrulanmadı.

**Kısıt (revize edildi):** Kullanıcı test grubuna ("ELAZIĞ MAVİ LOJİSTİK 1") mesaj yazma yetkisine sahip değil — grup üyesi/admin değil. Self-send de bu yüzden çalışmaz (test hesabı da o gruba yazamaz). **Çözüm:** Kullanıcı kendi telefonundan, test WhatsApp numarasına **doğrudan özel mesaj (DM)** gönderecek — kendi sohbeti, yazma izni sorunu yok.

**Yeni teknik detay:** `webhook_server.py`'nin mevcut `_handle_baileys_event` filtresi SADECE `data/chat_groups.json`'da kayıtlı **grup** ID'lerini (`@g.us`) kabul ediyor. Bir DM'in `chat_id`'si kişisel numara JID'i (`@s.whatsapp.net`) olacağı için bu filtre DM'i **reddedecek** — bu üretim davranışı doğru ve DEĞİŞMEYECEK. Bu testte SADECE test'e özel, geçici bir bypass kullanılacak: `test_receiver.py`'ye (üretim `webhook_server.py`'ye DEĞİL) bir ortam değişkeni (`TEST_ALLOW_CHAT_ID=<DM JID>`) ile tek seferlik bir istisna tanıtılacak. Üretim koduna hiçbir kalıcı değişiklik yapılmayacak.

## User Story
As a proje sahibi
I want Baileys→bridge→webhook→orchestrator zincirinin gerçek bir mesajla çalıştığının kanıtını
So that Whapi'den Baileys'e geçişin (epic #43) teknik olarak işe yaradığından emin olabileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given bağlı Baileys test oturumu (`auth_info_baileys/`), çalışan `bridge.js` ve `TEST_ALLOW_CHAT_ID=<kullanıcının DM JID'i>` ortam değişkeniyle başlatılmış `test_receiver.py`, When kullanıcı kendi telefonundan test WhatsApp numarasına benzersiz (UUID etiketli) bir özel mesaj (DM) gönderirse, Then bu mesaj `bridge.js` tarafından yakalanıp `/baileys-webhook`'a POST edilir ve `orchestrator.add_to_processing_queue()` log'unda görünür.
2. [Critical] Given DM gönderildi, When log'lar incelenirse, Then iki ayrı kanıt bulunmalı: (a) `bridge.js` konsolunda `[WEBHOOK OK]` satırı, (b) test receiver log'unda `[BAILEYS] 1 mesaj işleme kuyruğuna ekleniyor`.
3. [High] Given test mesajının benzersiz içeriği (UUID), When `data/mesajlar.json`/`islenmemis_mesajlar.json` kontrol edilirse, Then bu test mesajı orada bulunabilmeli (kuyruğa gerçekten eklendiğinin kanıtı) — test sonunda bu kayıt scriptli olarak temizlenmeli (bkz. Rollback).
4. [Critical] Given `TEST_ALLOW_CHAT_ID` bypass'ı sadece `test_receiver.py`'de (yeni eklenecek) devreye girer, When üretim `webhook_server.py`'nin `_handle_baileys_event` fonksiyonu incelenirse, Then bu env-var kontrolü orada da mevcutsa **varsayılan olarak boş/kapalı** olmalı — set edilmediği sürece üretim davranışı (sadece kayıtlı gruplar) hiç değişmemeli. Bu, testin üretim güvenliğini bozmadığının kanıtıdır.
5. [High] Given kullanıcı DM'i göndermeden önce, When `bridge.js` ve `test_receiver.py` henüz ayakta değilse, Then kullanıcıya "önce şu ikisini başlat" diye açık bir talimat verilir — mesaj erken gönderilirse (dinleyen yokken) bu bir "kayıp mesaj" değil, "henüz dinlenmiyordu" olarak ayrı raporlanır.
6. [Medium] Given test receiver ayakta değilse (bridge.js POST atarken connection refused alırsa), When bu olursa, Then `bridge.js` zaten var olan hata log'unu (`[WEBHOOK BAGLANTI HATASI]`) basar — bu davranış zaten mevcut, bu görev sadece gerçekten tetiklenip tetiklenmediğini gözlemler (aktif test senaryosu değil, pasif gözlem).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path — DM gönderildi, bridge yakaladı, webhook'a düştü, kuyruğa eklendi | `add_to_processing_queue()` başarıyla çağrıldı | Test mesajı `data/mesajlar.json`'a geçici olarak yazılır (test sonunda temizlenir) | 2 log satırı (bridge WEBHOOK OK, receiver BAILEYS kuyruk) | AC-1, AC-2 |
| 2 | Kullanıcı mesajı dinleyiciler ayakta olmadan önce gönderirse | Baileys mesajı normal şekilde alır ama `bridge.js` çalışmadığı için hiç yakalanmaz | Yok — mesaj WhatsApp'ta kalır, sisteme hiç girmez | Hiçbir log çıkmaz; kullanıcı "gönderdim ama bir şey olmadı" der | AC-5 |
| 3 | `test_receiver.py` ayakta değil (bridge.js POST atarken connection refused) | `bridge.js` zaten var olan `[WEBHOOK BAGLANTI HATASI]` log'unu basar | Mesaj Baileys'te yakalandı ama sisteme girmedi | Kullanıcı bridge.js konsolunda hata görür | AC-6 |
| 4 | `TEST_ALLOW_CHAT_ID` set edilmemiş/yanlış JID (kullanıcının gerçek DM JID'i değil) | Mesaj normal grup-filtresine tabi olur, DM olduğu için reddedilir | Yok | Test receiver'da hiçbir `[BAILEYS]` log satırı çıkmaz | AC-1 (dolaylı — test kurulumu hatası) |
| 5 | Kısmi başarı: DM webhook'a düştü ama `add_to_processing_queue()` içeride exception fırlatırsa | `_handle_baileys_event`'in mevcut try/except'i hatayı loglar (`Baileys webhook: kuyruğa ekleme hatası`), thread çöker ama server ayakta kalır | Mesaj kayboldu (kuyruğa girmedi) | Test receiver log'unda hata satırı | (mevcut kodda zaten var, bu görev sadece gerçek veriyle tetiklenip tetiklenmediğini doğruluyor) |

Kısmi başarı: Yukarıdaki satır 5 — bu zaten mevcut kodda try/except ile ele alınıyor, bu görev onu yeniden yazmıyor, sadece gerçek bir mesajla tetiklenebildiğini gözlemliyor.
Hiçbir şey yapılamadı ama hata da yok: **Kritik senaryo** — kullanıcı DM'i gönderir ama `bridge.js`'in `messages.upsert` event'i hiç tetiklenmezse (bağlantı kopmuşsa, session geçersizse) sistem sessizce hiçbir şey yapmaz. Bu AC-2'deki "iki ayrı kanıt" şartıyla ele alınıyor — ikisinden biri eksikse test BAŞARISIZ sayılır, "muhtemelen çalışıyordur" denmez. Kullanıcıya önce `bridge.js`'in `[BAGLANDI]` yazdığını görmesi söylenir (mesaj göndermeden ÖNCE).
Boş sonuç ↔ hata ayrımı: `data/mesajlar.json`'da test mesajı bulunamazsa, bu ya (a) dinleyiciler ayakta değilken gönderildi (AC-5) ya da (b) `TEST_ALLOW_CHAT_ID` yanlış/eksik ayarlandı (satır 4) ya da (c) gönderildi+yakalandı ama kuyruğa eklenirken hata oldu (satır 5) — üçü ayrı ayrı raporlanır, tek bir "başarısız" cümlesiyle geçiştirilmez.

## Test Strategy
Unit: 0% — bu görev yeni iş mantığı yazmıyor, mevcut kodun gerçek veriyle çalıştığını doğruluyor.
Integration: 30% — bridge.js↔webhook_server.py HTTP entegrasyonu (zaten mock ile test edildi, Saga #350).
E2E: 70% — Baileys gerçek bağlantı → kullanıcının gerçek DM'i → bridge → webhook (test bypass'lı) → orchestrator kuyruğu tam zinciri.

## Benchmark / Başarı Ölçütü
Coverage Target: n/a
Performance Target: yok
Diğer ölçülebilir kriterler:
- 2/2 log kanıtı bulunmalı (bridge WEBHOOK OK, receiver BAILEYS kuyruk).
- Test mesajı `data/mesajlar.json`'da benzersiz içeriğiyle (UUID) bulunabilmeli.
- Test sonrası bu test kaydı temizlenmiş olmalı (production verisi kirlenmemeli).
- `TEST_ALLOW_CHAT_ID` set edilmediğinde üretim davranışının (sadece kayıtlı gruplar) değişmediği doğrulanmalı (AC-4).

## Kapsam Dışı
- Gerçek Gemini/Groq API'sinin tetiklenip parser'ın gerçekten ayrıştırma sonucu üretmesi — bu görev sadece kuyruğa girene kadarki zinciri doğruluyor, maliyetli asıl ayrıştırmayı değil.
- Negatif senaryoların (satır 3, "webhook kapalıyken ne olur") aktif olarak test edilmesi — bu davranış zaten kodda var ve mantığı doğrulandı, bu görev sadece happy path'i gerçek veriyle kanıtlamaya odaklanıyor, pasif gözlem yeterli.
- Epic #44 (risk paritesi/Safety Meter eşdeğeri) — ayrı bir epic, bu görevin kapsamında değil.
- Üretim numarasıyla herhangi bir test — bu görev sadece mevcut test/ikincil numarayla yapılır.
- `TEST_ALLOW_CHAT_ID` bypass'ının kalıcı olarak koda bırakılması — test sonrası kaldırılmalı (bkz. Rollback) veya en azından net şekilde "TEST ONLY" yorumuyla işaretlenmeli.

## Etkilenen Dosyalar/Modüller (bilinen)
- `sidecar/bridge.js` (mevcut, değişmeyecek)
- `src/api/webhook_server.py` (`_handle_baileys_event`'e `TEST_ALLOW_CHAT_ID` ortam değişkeni kontrolü eklenecek — varsayılan boş/kapalı)
- `sidecar/test_receiver.py` (mevcut, önceki oturumda yazıldı — bu test için `TEST_ALLOW_CHAT_ID` ile başlatılacak)
- `data/mesajlar.json`, `data/islenmemis_mesajlar.json` (test sonunda temizlenecek test kaydı için)

## Rollback Beklentisi
Test mesajı benzersiz bir işaretle (örn. body içinde `[E2E-TEST-<uuid>]` etiketi) gönderilir. Test tamamlandıktan sonra bu ID'ye sahip kayıt `data/mesajlar.json` ve `data/islenmemis_mesajlar.json`'dan **script ile** (manuel değil) temizlenir — production verisiyle karışmasın diye. Test başarısız olursa da aynı temizlik yapılır. `TEST_ALLOW_CHAT_ID` sadece `test_receiver.py`'yi başlatırken ortam değişkeni olarak verilir, koda hard-code edilmez — süreç sonlanınca zaten etkisiz kalır, ayrıca kod değişikliği geri alınmaz (env-var default'u zaten kapalı).

## Risks
- Kullanıcının DM'i, `bridge.js` ve `test_receiver.py` ayakta değilken göndermesi riski var (AC-5) — bu yüzden kullanıcıya açık bir sıralı talimat verilecek: önce ikisini başlat, "[BAGLANDI]" görünce mesajı gönder.
- Test receiver'ın (`test_receiver.py`) gerçek orchestrator'ı kullanması, gerçek `data_service.mark_id_handled()` ve dosya yazma işlemlerini tetikler — tamamen yan etkisiz değil, bu yüzden Rollback adımı zorunlu.
- `TEST_ALLOW_CHAT_ID` bypass'ının yanlışlıkla üretim `webhook_server.py`'de aktif kalması — AC-4 bu riski azaltmak için var, ayrıca default'un boş olması kod incelemesiyle doğrulanacak.

## Assumptions
- Kullanıcı test WhatsApp numarasına DM gönderme konusunda herhangi bir kısıt yaşamıyor (kendi sohbeti, yetki sorunu yok) — bu, kullanıcının "yada yusuf yani ben sohbetim" ifadesinden çıkarıldı.
- (Haiku alt-ajanı önerisi) Kuyruğa eklenme kanıtı (log + dosyada bulunma) yeterli başarı kriteri — gerçek Gemini/Groq ayrıştırmasının çalıştığını kanıtlamaya gerek yok (o zaten mevcut production sisteminde kanıtlanmış).

## Unknowns
- Kullanıcının DM JID'inin tam formatı (`<numara>@s.whatsapp.net`) — test başlatılırken gerçek değerle doldurulacak, şu an placeholder.
- `test_receiver.py`'ye `TEST_ALLOW_CHAT_ID` env-var okumasının nasıl ekleneceği (doğrudan `_handle_baileys_event` içinde mi, yoksa `test_receiver.py`'nin kendi wrapper'ında mı) — plan aşamasında netleştirilecek, ikisi de AC-4'ü sağlar ama biri üretim koduna (webhook_server.py) dokunur, diğeri dokunmaz. **Tercih: mümkünse üretim dosyasına hiç dokunmadan, test_receiver.py'nin kendi seviyesinde filtrelemek** — daha güvenli.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü/persona → Proje sahibi, migration'ın üretime hazır olduğunu doğrulamak için. (Haiku alt-ajanı tarafından yanıtlandı)
2. Ana hedef/neden → Zincirin gerçek verilerle uçtan uca çalıştığını kanıtlamak. (Haiku alt-ajanı tarafından yanıtlandı)
3. Happy path senaryosu → İlk taslakta "self-send" önerildi (Haiku), ama kullanıcı düzeltti: test hesabının o gruba yazma yetkisi de yok. **Kullanıcı kararı: kendi telefonundan test numarasına DM göndermek** (kullanıcı mesajından, doğrudan).
4. Edge case 1 (dinleyiciler ayakta değilken mesaj gönderilirse) → Mesaj sisteme hiç girmez, sessiz kayıp olarak ayrı raporlanır (ATDD yazarken eklendi, self-send'in "gönderim başarısız" senaryosunun yerini aldı).
5. Edge case 2 (webhook'a düşmedi) → Bridge'in mevcut bağlantı hatası log'u yeterli, pasif gözlem (kullanıcı mesajından + Haiku).
6. Davranış sözleşmesi minimum kanıt → 2 log kanıtı (bridge + kuyruk) — self-send'deki "Baileys gönderim OK" kanıtı DM senaryosunda anlamsız olduğu için çıkarıldı.
7. Başarı ölçütü → 2/2 log kanıtı + dosyada bulunma + temizlik + üretim davranışının bozulmadığının doğrulanması (AC-4 eklendi).
8. Kapsam dışı → Gerçek Gemini/Groq ayrıştırması tetiklenmeyecek. (Haiku alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → bridge.js, webhook_server.py (TEST_ALLOW_CHAT_ID veya test_receiver.py seviyesinde filtre), add_to_processing_queue. (self_send_test.js kaldırıldı — DM senaryosunda gerek yok)
10. Rollback beklentisi → Evet, test verisi temizlenmeli — scriptli temizlik. Ayrıca TEST_ALLOW_CHAT_ID kalıcı koda hard-code edilmeyecek (kullanıcı mesajından çıkarılan ek kısıt: "çok açık bırakma").
11. Kabul kriteri sahibi → Proje sahibi. (Haiku alt-ajanı tarafından yanıtlandı)
12. Test stratejisi oranı → %0 unit / %30 integration / %70 e2e. (Haiku alt-ajanı tarafından yanıtlandı, senaryo değişse de oranlar geçerli kaldı)
