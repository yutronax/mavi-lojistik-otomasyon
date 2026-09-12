# Test Diff — baileys-sidecar-webhook-secret-header

## Oluşturulan Dosya
- `sidecar/test_webhook_secret_header.js` (yeni, 9 test fonksiyonu, Node built-in `assert`, `test_bridge_reliability.js` deseninde)

## AC → Test Eşlemesi
| AC | Test fonksiyonu |
|---|---|
| Export ön koşulu | `testPostToWebhookExported` |
| AC-1 (secret tanımlıyken header eklenir) | `testPostToWebhookHeaderWithSecret`, `testPostToWebhookHeaderExactValue`, `testPostToWebhookPreservesContentType` |
| AC-2 (secret tanımsızken header yok + uyarı) | `testPostToWebhookNoHeaderWithoutSecret`, `testPostToWebhookWarnsAboutMissingSecret` |
| AC-S1 (threat-model, secret log'a sızmaz) | `testPostToWebhookDoesNotLogSecretValue` |
| AC-3 (ağ hatası, mevcut davranış) | `testPostToWebhookErrorHandling` |
| Regresyon (WEBHOOK_URL kullanımı) | `testPostToWebhookFetchUrl` |

## İlk Çalıştırma Durumu (red step) — orkestratör tarafından bağımsız doğrulandı
`node sidecar/test_webhook_secret_header.js` → **exit 1**, ilk test (`postToWebhook` export edilmemiş) beklenen şekilde FAIL. Test runner fail-fast (`test_bridge_reliability.js` ile aynı desen), ilk hata sonrası durur — code-copilot export'u eklediğinde sıradaki testler çalışmaya başlayacak.

## Not
Test dosyası `global.fetch` ve `console.log/error/warn`'ı her test için mock'layıp sonra geri alıyor — testler birbirini kirletmiyor.
