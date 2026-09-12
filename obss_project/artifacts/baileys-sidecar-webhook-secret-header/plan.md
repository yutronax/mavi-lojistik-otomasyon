# Plan — baileys-sidecar-webhook-secret-header
_Reference: atdd.md_

Frontend-pipeline: tetikleyici yok (backend-only görev, UI/HTML/CSS yok).

## Kritik Keşif (deploy talimatını etkiliyor)
`ecosystem.config.js`'de `mavi-baileys-bridge` process'inin `env` bloğu (satır 46-49) sadece `NODE_ENV`/`WEBHOOK_URL` içeriyor. `bridge.js` `dotenv` KULLANMIYOR (grep ile doğrulandı, `sidecar/` içinde `dotenv` hiç yok) — yani VPS'in `.env` dosyasına `WEBHOOK_SHARED_SECRET` eklemek TEK BAŞINA bu process'e ulaşmaz (Python tarafındaki `vps_main.py`/`admin_panel.py`'nin aksine, onlar `load_dotenv()` çağırıyor). Bu yüzden atdd.md'nin "Kapsam Dışı" bölümündeki "VPS .env'e yazma kullanıcıya bırakılacak" ifadesi genişletiliyor: kullanıcıya verilecek deploy talimatı `.env` değil, **`ecosystem.config.js`'in `mavi-baileys-bridge` `env` bloğuna `WEBHOOK_SHARED_SECRET` eklemek** olmalı (VPS'teki dosyada, commit edilmeyecek — gerçek secret değeri git'e gitmemeli).

Yeni bir npm bağımlılığı (`dotenv`) eklemek CAVEMAN'a aykırı bir kapsam genişlemesi olur (bu görevin küçük, acil kapsamı için orantısız) — `process.env.WEBHOOK_SHARED_SECRET` doğrudan okunacak, PM2 `env` bloğundan gelecek şekilde.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| sidecar/bridge.js | AC-1/AC-2/AC-S1: `postToWebhook()`'a (satır 102-117) `process.env.WEBHOOK_SHARED_SECRET` okuma ve `X-Webhook-Secret` header'ı ekleme; secret tanımsızsa process başında bir kez uyarı; secret değeri hiçbir log çağrısına yazılmayacak. Test edilebilirlik için `postToWebhook` (veya header-oluşturma mantığı ayrı küçük bir fonksiyona çıkarılıp) `module.exports`'a (satır 298-305) eklenecek. | low |

## New Files
Yok.

## Dependencies
- `process.env.WEBHOOK_URL` deseniyle aynı şekilde `process.env.WEBHOOK_SHARED_SECRET` okunacak — yeni bağımlılık (dotenv vb.) EKLENMEYECEK.
- `module.exports` bloğu (satır 298-305) — mevcut `writeQrState`/`buildGetMessage` deseniyle tutarlı, yeni export eklenecek.
- Test deseni: `sidecar/test_bridge_reliability.js` — Node built-in `assert`, `require('./bridge.js')`, `require.main === module` guard'ı sayesinde test'te gerçek Baileys bağlantısı tetiklenmiyor. `sidecar/package.json`'da resmi bir test framework'ü (jest/vitest) YOK — `node <dosya>.js` ile çalıştırılıyor, `test-copilot` bu deseni birebir izleyecek.

## Migration Required?
Hayır. Kod değişikliği .env/DB şemasını değiştirmiyor. Ayrı bir OPERASYONEL adım var (yukarıdaki "Kritik Keşif") ama bu bir migration değil, deploy-zamanı env config'i.

## Risks
- (atdd.md'den taşındı) VPS `.env`'e `WEBHOOK_SHARED_SECRET` eklemek TEK BAŞINA yeterli DEĞİL — `ecosystem.config.js`'in `mavi-baileys-bridge` env bloğu da güncellenmeli (yukarıda detaylandırıldı). Deploy adımında kullanıcıya açıkça iki ayrı komut verilecek.
- `ecosystem.config.js` git'e commit'li bir dosya — gerçek secret değeri BU DOSYAYA yazılıp commit'lenmemeli. Kullanıcıya verilecek talimat VPS'teki ÇALIŞAN kopyayı (repo dizini içinde ama commit edilmeden) düzenlemesi yönünde olacak, ya da `pm2 set`/ortam değişkeni injection'ı önerilecek — kesin komut `verify`/deploy adımında netleştirilecek.

## Open Questions
Yok — kritik keşif zaten çözüldü (yukarıda), Sonnet 5 alt-ajanına dispatch gerekmedi (zaman kritik, kod okumasıyla netleşti).
