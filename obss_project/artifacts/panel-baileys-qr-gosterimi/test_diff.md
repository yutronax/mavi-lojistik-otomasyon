# Test Diff — panel-baileys-qr-gosterimi
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar

| Dosya | Framework | Çalıştırma |
|---|---|---|
| `tests/test_baileys_qr_panel.py` | pytest, `admin_panel.app.test_client()` | `python -m pytest tests/test_baileys_qr_panel.py -v` |
| `sidecar/test_baileys_qr_state.js` | Node builtin `assert` (framework yok, projedeki `risk_check.js` deseniyle tutarlı) | `node sidecar/test_baileys_qr_state.js` |

Her ikisi de şu an **RED** (başarısız) — `/api/whatsapp/qr` route'u ve bridge.js'in `writeQrState`/`writeAuthenticatedState` export'ları henüz yok. Bu beklenen durum.

## AC → Test Eşlemesi

| AC | Davranış | Python testi | JS testi |
|---|---|---|---|
| AC-1 | Happy path — QR mevcut, login'li → 200 + `need_auth` | `TestQrPanelHappyPath::test_qr_endpoint_200_with_valid_qr_file`, `test_qr_endpoint_response_structure` | `writeQrState` doğru format/atomic yazma testleri |
| AC-2 | Oturum açık → 200 + `authenticated` | `TestQrPanelAuthenticated::test_qr_endpoint_authenticated_status` | `writeAuthenticatedState` testleri |
| AC-3 | Yetkisiz erişim → 401 | `TestQrPanelAuth::test_qr_endpoint_401_without_token`, `_with_invalid_token`, `_with_expired_token` (gerçek `app.test_client()` + Bearer header ile, auth bypass EDİLMEDİ) | — (Flask tarafı) |
| AC-4 | Dosya yok → 202 + `waiting` | `TestQrPanelWaiting::test_qr_endpoint_202_file_not_found` | — |
| AC-5 | Dosya çok eski (>2dk) → `waiting` | `TestQrPanelOldFile::test_qr_endpoint_waiting_for_old_file` | — |
| AC-6 | Bozuk JSON → `waiting`, 500 DÖNMEZ | `TestQrPanelBrokenJson::test_qr_endpoint_broken_json_not_500`, `test_qr_endpoint_empty_file` | atomic write / cleanup testleri |

## code-copilot İçin Bağlayıcı Varsayımlar (Haiku alt-ajanının raporundan, birebir)

Bu isimlere UYULMALI — testler bunlara göre yazıldı:

- **Python**: sabit `admin_panel.BAILEYS_QR_PATH = os.path.join(PROJECT_ROOT, "data", "baileys_qr.json")`; route `/api/whatsapp/qr` (GET, `@require_auth`); auth hatası mesajı `{"error": "Yetkisiz"}` (mevcut `require_auth` dekoratörünün gerçek metni — atdd.md'deki `login_required` DEĞİL, koddaki gerçek davranışa uyuldu).
- **Node.js**: `sidecar/bridge.js` şu iki fonksiyonu `module.exports` ile dışa açmalı:
  - `writeQrState(qr, filePath = 'data/baileys_qr.json')`
  - `writeAuthenticatedState(filePath = 'data/baileys_qr.json')`
  - Her ikisi de atomic write (tmp+rename) kullanmalı.
- **Kritik ek gereksinim (JS test düzeltmesinden)**: bridge.js dosyasının en altındaki `bridge().catch(...)` çağrısı `if (require.main === module) { bridge().catch(...); }` guard'ına alınmalı — aksi halde `require('./bridge.js')` (testin veya başka bir modülün import etmesi) gerçek bir Baileys bağlantı denemesini tetikler. Bu, `manual_webhook_test_server.py`'nin `__main__` guard deseniyle birebir aynı önlem.

## Not
JS testinin ilk taslağı bridge.js'i hiç `require` etmeyip kendi yerel mock'unu test ediyordu (red-step'i anlamsızlaştıran bir hata) — tespit edilip ikinci bir Haiku dispatch'iyle düzeltildi, artık gerçek `require('./bridge.js')` export'larına karşı test ediyor.
