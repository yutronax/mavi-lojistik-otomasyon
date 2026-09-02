# Test Diff — panel-baileys-oturum-kapat
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_baileys_disconnect_panel.py` — 18 test fonksiyonu, `tests/test_baileys_qr_panel.py`'nin (önceki görev) aynı deseniyle (pytest, `admin_panel.app.test_client()`, Bearer token simülasyonu, `patch.object`).

Şu an **RED** (başarısız) — `/api/whatsapp/disconnect` route'u henüz yok.

## AC → Test Eşlemesi
| AC | Davranış | Test Fonksiyonları |
|---|---|---|
| AC-1 | Happy path — silinir, pm2 restart başarılı → 200/logged_out | `TestDisconnectHappyPath::test_disconnect_happy_path_with_real_directory`, `test_disconnect_happy_path_response_structure` |
| AC-2 | Zaten kopuk (idempotent) → 200/already_logged_out | `TestDisconnectAlreadyDisconnected::test_disconnect_idempotent_directory_not_found`, `test_disconnect_idempotent_error_message_not_shown` |
| AC-3 | Yetkisiz erişim → 401 | `TestDisconnectAuth` (4 test: token yok/geçersiz/süresi dolmuş/malformed) |
| AC-4 | Dosya silme başarısız → 500/file_delete | `TestDisconnectFileDeletionError` (3 test) |
| AC-5 | Kısmi başarı (silindi, pm2 başarısız) → 500/pm2_restart/file_deleted:true | `TestDisconnectPartialSuccess` (3 test) |
| AC-6 | Confirm dialog | Backend testinde YOK (frontend-only, bilinçli atlandı — `verify` adımında canlı tarayıcıyla kontrol edilecek) |

Ek: method/auth-scheme edge case testleri (4 adet).

## code-copilot İçin Bağlayıcı Varsayımlar (test dosyasından, birebir)
- Route: `POST /api/whatsapp/disconnect`, `@require_auth`
- Yeni sabit: `admin_panel.BAILEYS_AUTH_DIR = os.path.join(PROJECT_ROOT, "sidecar", "auth_info_baileys")`
- PM2 çağrısı: `_pm2(["restart", "mavi-baileys-bridge"])` (mevcut `_pm2()` yardımcı fonksiyonu, satır 133-139)
- Response şekli: `{"ok": true/false, ...}` — `"success"` DEĞİL (plan.md'deki proje-konvansiyon kararı)
- Auth hata mesajı: `{"error": "Yetkisiz"}` (mevcut `require_auth` dekoratörünün gerçek metni)
- Sıra: dosya silme İLK denenir; başarısız olursa pm2 restart HİÇ denenmez (AC-4 testinde doğrulanıyor — `_pm2` mock'unun HİÇ çağrılmadığı assert ediliyor).
