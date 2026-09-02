# Plan — panel-baileys-qr-gosterimi
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| sidecar/bridge.js | `connection.update` handler'ına (satır 127-133) QR üretildiğinde `data/baileys_qr.json`'a `{qr: <base64 PNG data URI>, generated_at: <epoch ms>}` yazma eklenir; `connection === 'open'` olduğunda (satır 157-159) aynı dosyayı `{status: "authenticated"}` ile güncelleyip QR alanını temizler. AC-1, AC-2. | low |
| sidecar/package.json | `qrcode` (PNG/data-URI üretimi) bağımlılığı eklenir — mevcut `qrcode-terminal` sadece ASCII üretiyor, PNG üretemiyor. AC-1. | low |
| src/api/admin_panel.py | Yeni route `/api/whatsapp/qr` eklenir (mevcut `/api/whatsapp-health` route'unun yanına, ~satır 786'dan sonra), `@require_auth` dekoratörüyle korunur (mevcut Bearer-token deseni, satır 119-129). `data/baileys_qr.json` okunur, AC-1/2/3/4/6'daki durum makinesine göre response üretilir. `INDEX_HTML` sabitine (dosyanın üst kısmında tanımlı, `/` route'unun döndürdüğü) QR gösterme bölümü + 4 saniyelik polling JS eklenir. | medium |

## New Files
| File | Purpose |
|------|---------|
| data/baileys_qr.json | bridge.js'in yazdığı, admin_panel.py'nin okuduğu paylaşılan QR durumu (`{qr, generated_at}` veya `{status: "authenticated"}`). VPS'te `data/` klasörü deploy script'inde (`deploy_vps.ps1`, `--exclude="data"`) zaten korunan/kalıcı bir konum. |

## Dependencies
- `src/api/admin_panel.py`: mevcut `@require_auth` dekoratörü (satır 119-129, Bearer token — `Authorization: Bearer <token>` header, `TOKENS` dict'inde epoch expiry kontrolü) birebir kullanılacak — yeni bir auth mekanizması İCAT EDİLMEYECEK.
- `_atomic_write()` yardımcı fonksiyonu (admin_panel.py satır 141-146) zaten var ama bu Python tarafı için; bridge.js tarafında Node'da eşdeğer bir atomic-write (geçici dosya + `fs.renameSync`) uygulanmalı — AC-6'daki "bozuk JSON okuma" riskini bridge.js YAZMA tarafında da azaltır (admin_panel.py READ tarafında zaten try/except ile ele alınacak).
- Mevcut hata-yutma deseni: `whatsapp_health()` (satır 755-785) network hatalarını try/except ile yutup `{"status": "error", "detail": ...}` döndürüyor — aynı desen `/api/whatsapp/qr`'da JSON parse hatası için kullanılacak (AC-6, "waiting" durumuna düşürme).
- `sidecar/package.json`: yeni `qrcode` paketi (PM2 restart'ta `npm install --omit=dev` zaten `deploy_vps.ps1`'de çalışıyor, ek bir deploy adımı gerekmiyor).

## Migration Required?
No — şema/DB değişikliği yok, sadece yeni bir JSON dosyası (kendi kendini tanımlayan, migration gerektirmeyen) ve yeni bir Flask route.

## Risks
(atdd.md'den taşındı, ek bulgu yok)
- İki ayrı PM2 process (bridge.js/Node, admin_panel.py/Python) arasında dosya tabanlı paylaşım race condition'a açık — admin_panel.py READ tarafında try/except ile "waiting" durumuna düşürülerek hafifletiliyor; bridge.js YAZMA tarafında da atomic write (tmp+rename) ile ayrıca hafifletilecek (plan'da yeni eklenen önlem).
- QR görselinin gerçek taranabilirliği (boyut/kontrast) otomatik testle doğrulanamaz — bu bir HTML/frontend değişikliği içerdiği için (`INDEX_HTML` içindeki QR bölümü) `verify` adımında gate 11 (`vision-test`) N/A değil AKTİF çalışmalı; ayrıca manuel/gerçek telefon testi önerilir.

## Open Questions
Yok — atdd.md'nin tek "Unknown"u (login mekanizmasının tam şekli) kod okunarak netleşti: `require_auth` dekoratörü Bearer-token tabanlı (session cookie DEĞİL). Bu, `test-copilot`'un Flask test client testlerinde `Authorization: Bearer <token>` header'ı kullanması gerektiği anlamına gelir. Haiku/claude-omni dispatch'ine gerek kalmadı.
