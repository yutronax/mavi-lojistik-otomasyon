---
task_slug: pm2-process-izleme-ve-uyari
jira_id: null
saga_task_id: 375
priority: high
coverage_target: 80
performance_target: "<5 dakika (düşme -> bildirim)"
memory_target: null
test_strategy:
  unit: 70
  integration: 20
  e2e: 10
affected_modules:
  - src/api/admin_panel.py
---

# ATDD — pm2-process-izleme-ve-uyari

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #375 (epic #52 "Altyapı İzleme
ve Uyarı", proje: maviLojistik).

## Persona
Sistem operatörü (kullanıcının kendisi) — VPS'i uzaktan yönetiyor, admin
panele ve kendi WhatsApp numarasına erişimi var.

## Hedef (Neden)
Bugün canlı olarak `mavi-baileys-bridge` (WhatsApp bağlantısı) PM2
listesinden **tamamen düşmüştü** (crash-loop/errored değil, `pm2 list`
çıktısında hiç görünmüyordu). Kullanıcı bunu **manuel** fark etti —
"ben fark etmeseydim gün boyu düzelmeyecekti" dedi. Kök neden kesin
bulunamadı (sunucu 22 gündür reboot olmamıştı, `~/.pm2/dump.pm2`'de bu
process hiç kayıtlı değildi, `dmesg`'de OOM kanıtı yoktu ama kernel ring
buffer muhtemelen dönmüştü). Bu görev kök nedeni çözmüyor — bunun yerine
**gelecekte aynı durum tekrar olursa kimsenin fark etmeden saatlerce/gün
boyu geçmemesini** sağlıyor: periyodik bir sağlık kontrolü + otomatik
bildirim.

## User Story
As a sistem operatörü
I want VPS'teki 3 PM2 process'inin (mavi-lojistik-server, mavi-admin-panel,
mavi-baileys-bridge) durumunun periyodik kontrol edilip biri "online"
değilse otomatik bildirim almayı
So that bir process sessizce düşerse (crash, silinme, PM2 listesinden
kaybolma) bunu dakikalar içinde öğrenip müdahale edebileyim, WhatsApp
mesajları saatlerce işlenmeden kaybolmasın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given 3 beklenen process (`mavi-lojistik-server`,
   `mavi-admin-panel`, `mavi-baileys-bridge`) `pm2 jlist` çıktısında hepsi
   `status: "online"`, When periyodik kontrol (2-5 dakikada bir) çalışır,
   Then hiçbir bildirim gönderilmez — sadece iç durum (`_process_health`
   cache) sessizce güncellenir.
2. [Critical] Given bu 3 process'ten biri `pm2 jlist` çıktısında YA hiç
   yok YA DA `status` "online" değil, When kontrol bunu tespit eder, Then
   `/api/status`'a `process_health` alanı bu process'i "down" olarak
   işaretler (bkz. plan.md kararı: bu iterasyonda WhatsApp/Discord gibi
   dış bildirim kanalı YOK — bridge.js'e yeni kod eklemenin riski
   nedeniyle bilinçli olarak panel-only'e daraltıldı, ayrı bir takip
   görevi olarak not düşüldü).
3. [Critical] Given bir process için az önce (30 dakikadan kısa süre önce)
   zaten "down" olarak işaretlenmiş, When aynı process hâlâ down durumda
   kontrol edilir, Then `process_health`'teki durum güncel tutulur (yeni
   bir "olay" tetiklenmez — bu AC'nin asıl amacı gelecekteki bildirim
   kanalı için debounce ALTYAPISINI şimdiden doğru kurmak, log/durum
   spam'i önlemek).
4. [High] Given daha önce "down" işaretlenmiş bir process, When bir
   sonraki kontrolde tekrar "online" olduğu görülür, Then
   `process_health` "ok" olarak güncellenir ve debounce durumu sıfırlanır
   (WhatsApp/Discord "düzeldi" mesajı YOK — bkz. AC-2 notu, panel-only
   kapsam).
5. [High] Given `pm2 jlist` komutu tamamen başarısız olur (subprocess
   hatası), When health-check bunu tespit eder, Then bu durum "down"
   DEĞİL, ayrı bir "unknown"/"izleme arızalı" durumu olarak
   `process_health`'e yazılır — sessizce yutulmaz, "her şey online"
   gibi de görünmez.

## Davranış Sözleşmesi (hangi durumda ne döner)
Bu bir arkaplan izleme mekanizması — dış girdi/HTTP endpoint yok, tek
temas noktası mevcut `/status` endpointinin genişletilmesi.

| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: 3 process de online | N/A (arkaplan) | `process_health` cache güncellenir | `/status`'ta `process_health: {mavi-lojistik-server: "ok", mavi-admin-panel: "ok", mavi-baileys-bridge: "ok"}` | AC-1 |
| 2 | Bir process down (ilk tespit) | N/A | `process_health`'te o process "down" işaretlenir + `down_since` zaman damgası kaydedilir | Panelde down process görünür | AC-2 |
| 3 | Aynı process hâlâ down, debounce penceresi içinde | N/A | Durum güncellenmeye devam eder, `down_since` DEĞİŞMEZ (ilk tespit zamanı korunur) | Panelde hâlâ "down", ne zamandan beri düştüğü görünür | AC-3 |
| 4 | Down process tekrar online oldu | N/A | `process_health` "ok"a döner, `down_since` temizlenir | Panelde "ok" | AC-4 |
| 5 | `pm2 jlist` komutu tamamen başarısız (subprocess hatası/timeout) | N/A | 3 process de "unknown" olarak işaretlenir — "down" DEĞİL | Panelde "unknown" — "down" ile karıştırılmaz, "her şey online" da GÖRÜNMEZ | AC-5 |

Kısmi başarı: `pm2 jlist` 3 process'ten sadece bir kısmını döndürürse
(ör. listede sadece 2 process var), listede hiç GÖRÜNMEYEN process de
"down" sayılır (AC-2 ile aynı — PM2 listesinden tamamen düşmek, bugünkü
canlı olayın ta kendisi).
Hiçbir şey yapılamadı ama hata da yok: `pm2 jlist` komutu tamamen
başarısız olursa (subprocess hatası/timeout/JSON parse hatası), TÜM
process'ler "unknown" olarak işaretlenir — sessiz başarı YASAK, "her şey
online" gibi YANLIŞ bir izlenim verilmez.
Boş sonuç ↔ hata ayrımı: "unknown" (pm2 komutunun kendisi çalışmadı,
hiçbir process hakkında bilgi yok) ile "down" (pm2 çalıştı, process'in
online OLMADIĞI kesin tespit edildi) ayrı durumlardır — ikisi de aynı
görünmez.

## Test Strategy
Unit: 70% — health-check mantığı (`pm2 jlist` çıktısını mock'layarak:
3'ü de online → bildirim yok; biri down → bildirim tetiklenir; debounce
süresi dolmadan tekrar down → bildirim yok; düzelme → "düzeldi" bildirimi;
parse hatası → "unknown"; subprocess hatası → "izleme arızalı" bildirimi)
Integration: 20% — `/api/status` endpointinin yeni `process_health`
alanını doğru döndürmesi, debounce state'inin zaman içinde (mock'lanmış
saat) doğru işlemesi
E2E: 10% — gerçek PM2/WhatsApp'a çağrı yapılmaz (maliyetli/gereksiz);
gerçek doğrulama kullanıcının VPS'te bilerek bir process durdurup
bildirimin geldiğini görmesiyle yapılacak (kod dışı)

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: Bir process düştükten sonra en geç 5 dakika içinde
bildirim üretilmeli (kontrol periyodu 2-5dk + debounce ile tutarlı).
Memory: yok
Diğer ölçülebilir kriterler:
- Kabul kriteri onayı: kullanıcı + otomatik testler (mock'lu). Gerçek
  VPS'te canlı doğrulama (bilerek bir process durdurma) kullanıcının
  kendi gözlemine kalıyor, bu ortamda doğrulanamaz.

## Kapsam Dışı
- **WhatsApp/Discord gibi dış bildirim kanalı — plan.md aşamasında
  bilinçli olarak ERTELENDİ** (kullanıcı onayıyla, seçenek B).
  `sidecar/bridge.js`'te mesaj GÖNDERME endpointi hiç yoktu — eklemek
  bugün kırılganlığını gördüğümüz bu dosyaya yeni kod eklemek anlamına
  geliyordu. `notification_service.py`'deki hazır `DiscordNotifier` da
  VPS'te aktif değildi (yeni kanal kurulumu sayılır). Bu görev SADECE
  admin panel `/api/status`'a `process_health` alanı ekliyor — dış
  bildirim ayrı bir takip görevi (Saga'da not düşülecek).
- Process'i **otomatik yeniden başlatma** (auto-heal) — ayrı ve daha
  riskli bir görev, bu görev sadece TESPİT yapar.
- Kök neden analizi/OOM önleme (`max_memory_restart` değerlerinin VPS'in
  gerçek RAM'inden yüksek olması gibi bulgular — ayrı bir görev/backlog).
- Yeni bir bildirim kanalı (Telegram bot, email) kurulumu — sadece mevcut
  kanallar (WhatsApp kendine mesaj + admin panel `/status`) kullanılacak.
- Debounce state'inin restart'lar arası kalıcı olması — in-memory yeterli
  kabul ediliyor, süreç restart olursa debounce sıfırlanır (bilinen
  sınırlama, aşağıda Risks'te).

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` — mevcut `_refresh_status_cache` (satır
  ~180-218, `pm2 jlist` zaten okunuyor) genişletilecek veya yeni bir
  `_refresh_process_health` poller'ı eklenecek; `/api/status` handler'ı
  yeni `process_health` alanı dönecek.

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımından önce `git rev-parse --show-toplevel` ile
tekrar doğrulanmalı; arama maviLojistik worktree kökü ile sınırlı
tutulmalı.

## Rollback Beklentisi
Additive bir izleme özelliği — mevcut hiçbir işlevi bozmuyor (mevcut
`/status` alanları değişmiyor, sadece yeni alan ekleniyor). Hata
durumunda `git revert` yeterli, veri kaybı riski yok.

## Risks
- **Döngüsel bağımlılık (bilinen sınırlama):** WhatsApp bildirim kanalı
  tam da `mavi-baileys-bridge`'in kendisi düştüğü anda çalışmayamayabilir
  — bu durumda panel banner'ı (fallback) tek güvenilir kanal kalır.
  AC-5 bu durumu açıkça ele alıyor (sessizce yutulmuyor).
- Debounce state'i in-memory — süreç (mavi-admin-panel) restart olursa
  sıfırlanır, kısa bir pencerede tekrar bildirim gidebilir. Kabul
  edilebilir sınırlama olarak işaretleniyor, bu görevde çözülmüyor.
- Kernel ring buffer dönmüş olduğu için process'in neden düştüğü (OOM mü,
  manuel `pm2 delete` mi) kesin belirlenemiyor — bu görev bunu ÇÖZMÜYOR,
  sadece gelecekte benzer olayı erken yakalıyor.
- **`EXPECTED_PM2_PROCESSES` sabit/hardcoded liste** (red-team incelemesinde
  bulundu) — gelecekte VPS'e dördüncü bir PM2 process eklenirse, bu liste
  MANUEL güncellenmezse o process hiç izlenmez (bugünkü olayın "yeni
  eklenen ama unutulan process" versiyonu sessizce tekrar edebilir).
  Dinamik keşif (PM2'nin kendisinden "beklenen" listeyi türetme) bu
  görevin kapsamında değil, bilinçli bir basitleştirme.

## Assumptions
- Kullanıcı admin panele erişimi olan tek kişi — "kullanıcıya bildirim"
  = kullanıcının kendi WhatsApp numarasına mesaj anlamına geliyor.
- Mevcut `_refresh_status_cache`'in `pm2 jlist` okuma mantığı doğru
  çalışıyor (bu görev onu değiştirmiyor, üzerine health-check ekliyor).

## Unknowns
- `mavi-baileys-bridge`'in düşmesinin kesin kök nedeni (OOM/manuel silme)
  — bu görevin kapsamı dışında, ayrı bir investigation gerektirebilir.

## Sorular ve Cevaplar (ham kayıt)
1. Persona → Sistem operatörü/kullanıcının kendisi (Sonnet 5 low
   alt-ajanı tarafından yanıtlandı)
2. Ana hedef/neden → Process sessizce düşünce kimse fark etmiyor,
   bugünkü olay bunu kanıtladı (Sonnet 5 low alt-ajanı tarafından
   yanıtlandı)
3. Happy path → 2-5dk'da bir `pm2 jlist` kontrolü, hepsi online ise
   sessiz (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
4. Edge case (process down) → hem `/status` alanı hem WhatsApp bildirimi,
   döngüsel bağımlılık bilinerek (Sonnet 5 low alt-ajanı tarafından
   yanıtlandı)
5. Edge case (spam önleme) → 30dk debounce + düzelme bildirimi (Sonnet 5
   low alt-ajanı tarafından yanıtlandı)
6. Davranış sözleşmesi → yukarıdaki tablo (Sonnet 5 low alt-ajanı
   tarafından dolduruldu/düzeltildi)
7. Başarı ölçütü → 5 dakika içinde bildirim, coverage %80 (Sonnet 5 low
   alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → auto-heal, kök neden analizi, yeni kanal kurulumu
   (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → admin_panel.py, in-memory debounce yeterli (Sonnet 5
   low alt-ajanı tarafından yanıtlandı)
10. Performans/güvenlik kısıtı → yok (Sonnet 5 low alt-ajanı tarafından
    yanıtlandı)
11. Rollback → git revert yeterli, additive (Sonnet 5 low alt-ajanı
    tarafından yanıtlandı)
12. Kabul kriteri sahibi → kullanıcı + otomatik testler, canlı doğrulama
    kullanıcıya kalıyor (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
13. Test stratejisi → 70/20/10 (Sonnet 5 low alt-ajanı tarafından
    yanıtlandı)
14. Riskler/varsayımlar → döngüsel bağımlılık bilinen sınırlama, tek
    kullanıcı varsayımı, kök neden hâlâ bilinmiyor (Sonnet 5 low
    alt-ajanı tarafından yanıtlandı)
