# Code Diff — baileys-sidecar-webhook-secret-header

## Değiştirilen Dosya
- `sidecar/bridge.js`

## AC → Kod Karşılığı
- **AC-1**: `postToWebhook`'ta `process.env.WEBHOOK_SHARED_SECRET` okunuyor, tanımlıysa `headers['X-Webhook-Secret']` ekleniyor (mevcut `Content-Type` korunuyor).
- **AC-2**: Modül yüklenirken (fonksiyon her çağrıldığında değil, bir kez) `WEBHOOK_SHARED_SECRET` tanımsızsa `console.warn` ile net uyarı.
- **AC-3**: Mevcut try/catch (ağ hatası) dokunulmadı.
- **AC-S1 (threat-model)**: Secret'in gerçek değeri hiçbir log çağrısına yazılmıyor — sadece "tanımlı değil" durumu statik bir mesajla loglanıyor, header adı (`X-Webhook-Secret`) loglanabilir ama değeri asla.
- Yeni npm bağımlılığı yok (`dotenv` eklenmedi, `process.env` doğrudan okundu — plan.md'nin kararına sadık kalındı).
- `postToWebhook` `module.exports`'a eklendi (test edilebilirlik).

## Doğrulama
- `node sidecar/test_webhook_secret_header.js` → **9/9 PASS** (orkestratör tarafından bağımsız çalıştırıldı).
- `node sidecar/test_bridge_reliability.js` → **9/9 PASS** (regresyon yok, mevcut testler etkilenmedi).
- `git diff HEAD -- sidecar/bridge.js` okunarak diff'in minimal olduğu doğrulandı: 3 küçük, bağımsız değişiklik (startup uyarısı, header ekleme, export).

## Kalan Sınırlamalar (bilinçli, kapsam dışı)
- VPS'te gerçek `WEBHOOK_SHARED_SECRET` değerinin ayarlanması bu görevin kapsamı dışında — kullanıcıya deploy adımı olarak verilecek (plan.md "Kritik Keşif": `.env` değil, `ecosystem.config.js`'in `mavi-baileys-bridge` env bloğu).

## CAVEMAN Self-Review
- Yeni dosya, yeni soyutlama, yeni yardımcı fonksiyon yok.
- Diff 3 küçük, bağımsız değişiklik: (1) startup-time uyarı, (2) header ekleme, (3) export.
- Mevcut davranış (Content-Type, error handling, WEBHOOK_URL) değişmedi.
