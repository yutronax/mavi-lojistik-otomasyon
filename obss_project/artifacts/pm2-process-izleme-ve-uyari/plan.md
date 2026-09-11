# Plan — pm2-process-izleme-ve-uyari
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | `_refresh_status_cache` (satır 176-218) **sadece `SERVICE_NAME` (mavi-lojistik-server) tek process'ini** filtreliyor — diğer ikisi (`mavi-admin-panel`, `mavi-baileys-bridge`) hiç kontrol edilmiyor. Yeni bir health-check mantığı (3 process'in hepsini kontrol eden) eklenecek, `/api/status`'a `process_health` alanı dönecek. | medium — mevcut `_status_cache` yapısını bozmadan genişletmek gerekiyor (geriye dönük uyumluluk) |

## New Files
Yok (bu iterasyonda — bkz. Open Questions, WhatsApp gönderim kanalı ayrı bir dosya/servis gerektirebilir).

## Dependencies
- `_pm2(args)` (admin_panel.py:135-141) — zaten var, `subprocess.run(["pm2"] + args, ...)` ile PM2 komutu çalıştırıp `(ok, output)` döner. Yeni health-check bunu aynen kullanacak (`_pm2(["jlist"])`).
- `_status_cache` global + `status-poller` thread deseni — yeni `process_health` mantığı bu AYNI thread içine eklenecek (ayrı bir thread AÇILMAYACAK, zaten 8sn'de bir `pm2 jlist` çağrılıyor, aynı veriyi tekrar çekmek gereksiz).
- `logger` — bildirim gönderilemediğinde loglamak için (AC-5).

## Kritik Bulgu — WhatsApp Gönderim Kanalı Mevcut Değil
`sidecar/bridge.js` YALNIZCA gelen mesajları webhook'a iletiyor — mesaj
**gönderme** (`sock.sendMessage()`) için hiçbir HTTP endpoint yok. ATDD'nin
AC-2/AC-4'ü ("kullanıcının kendi WhatsApp numarasına uyarı mesajı
gönderilir") bunu VARSAYMIŞTI ama koddan doğrulanamadı — bu, `bridge.js`'e
YENİ bir endpoint eklemeyi gerektirir (Node.js tarafı, farklı runtime,
bugün tam da kırılganlığını gördüğümüz bir dosya).

Alternatif olarak `src/utils/notification_service.py` içinde HAZIR bir
`NotificationService` bulundu — `DiscordNotifier` (webhook tabanlı,
WhatsApp/Baileys'ten TAMAMEN bağımsız, döngüsel bağımlılık riski yok).
Ama `DISCORD_WEBHOOK_URL` ne `.env.example`'da ne VPS'te (bilgimiz
dahilinde) tanımlı — yani bu "mevcut aktif kanal" değil, "yeni kanal
kurulumu" sayılır, ATDD'nin Kapsam Dışı kararına (yeni kanal kurulumu
YAPILMAYACAK) göre bu görevde KULLANILAMAZ.

## Migration Required?
Hayır — JSON/env tabanlı bir proje, şema migration kavramı yok.

## Risks
(atdd.md'den taşınan + planlama sırasında netleşen)
- **Bridge.js'e yeni endpoint eklemek risk taşıyor** — bugün tam da bu
  dosyanın (PM2'den düşme, decrypt hataları) kırılgan olduğunu gördük.
  Yeni bir HTTP sunucu/endpoint eklemek (kimlik doğrulama, port çakışması,
  ek bağımlılık) bu kırılganlığı artırabilir.
- Mevcut `_refresh_status_cache`'in SADECE 1 process'i izlemesi zaten bir
  "sessiz kör nokta" — bu görev bunu düzeltiyor ama aynı fonksiyonun
  başka bir yerde (varsa) `SERVICE_NAME`'e özel davrandığı varsayımına
  dikkat edilmeli.
- In-memory debounce state, `mavi-admin-panel` restart olursa sıfırlanır
  (ATDD'de zaten bilinen sınırlama olarak işaretli).

## Open Questions
**Bu soru code-copilot'tan ÖNCE kullanıcıya sorulmalı — teknik bir
detay değil, gerçek bir kapsam/risk kararı:**

WhatsApp gönderim kanalı (AC-2/AC-4) için 3 seçenek var:

**A) Bridge.js'e yeni `/send-message` endpoint'i ekle** — ATDD'nin
   orijinal isteğini birebir karşılar, ama bugün kırılganlığını gördüğümüz
   dosyaya yeni kod eklemek riski var.

**B) Bu iterasyonda WhatsApp gönderimini ATLA, sadece admin panel
   `process_health` alanını ekle** — AC-2/AC-4'ü "panel banner'ı" kısmıyla
   kısmen karşılar, WhatsApp bildirimi ayrı bir sonraki görev olur (daha
   güvenli, küçük adım). Kullanıcı panele bakmazsa bildirim kaçırılabilir
   ama bu bugünkü "hiç izleme yok" durumundan çok daha iyi bir başlangıç.

**C) `notification_service.py`'deki `DiscordNotifier`'ı aktifleştir**
   (ATDD'nin Kapsam Dışı kararına aykırı ama en düşük riskli ve zaten
   kodlanmış — sadece `DISCORD_WEBHOOK_URL` env değişkeni + Discord'da
   bir webhook oluşturmak gerekiyor, kullanıcı tarafında birkaç dakikalık
   kurulum).

Öneri: **B** — en düşük risk, en hızlı teslim, mevcut kırılgan dosyaya
dokunmuyor. WhatsApp/Discord bildirimi ayrı bir takip görevi olarak
Saga'ya not düşülür.
