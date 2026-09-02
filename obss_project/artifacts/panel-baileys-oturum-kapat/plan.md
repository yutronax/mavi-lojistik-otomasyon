# Plan — panel-baileys-oturum-kapat
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | Yeni route `/api/whatsapp/disconnect` (POST, `@require_auth`) eklenir — mevcut `_pm2(args)` yardımcı fonksiyonunu (satır 133-139) ve `/api/service/<action>` route'unun (satır 275-288) desenini takip eder. `INDEX_HTML` sabitine (mevcut `baileys-qr-section`'ın yanına) "Bağlantıyı Kes" butonu + `confirm(...)` onay dialogu eklenir (mevcut `deleteMsg()`/grup silme/blacklist silme fonksiyonlarındaki AYNI `if(!confirm(...))return;` deseni, satır 1489/1501/1596/1680 civarı). AC-1..AC-6. | low |

## New Files
Yok.

## Dependencies
- `_pm2(args)` (admin_panel.py satır 133-139): `subprocess.run(["pm2"] + args, ...)`, `(success, output)` döner — `pm2 restart mavi-baileys-bridge` için birebir kullanılacak.
- `BAILEYS_QR_PATH`/panel-baileys-qr-gosterimi görevinin QR bölümü (satır ~1222-1226, ~1529-1552) — disconnect sonrası panel bu bölümün otomatik olarak "waiting" durumuna döneceğini (mevcut 4sn polling zaten bunu yapıyor) VARSAYAR, ayrı bir UI güncellemesi gerekmez.
- `auth_info_baileys/` klasör yolu: `sidecar/auth_info_baileys/` (bridge.js'in `useMultiFileAuthState(path.join(__dirname, 'auth_info_baileys'))` çağrısıyla aynı yol, `sidecar/bridge.js` satır 117 civarı) — admin_panel.py'den `os.path.join(PROJECT_ROOT, "sidecar", "auth_info_baileys")` olarak silinecek.
- Python `shutil.rmtree(path, ignore_errors=False)` — klasör silme için (proje genelinde başka bir "recursive delete" yardımcı fonksiyonu YOK, doğrudan stdlib kullanılacak).

## Migration Required?
No — şema/DB değişikliği yok.

## Kararlar (mevcut kod deseniyle uyum için, atdd.md'nin varsayımlarını netleştiriyor)
1. **Response şekli değişti**: atdd.md `{"success": true/false, ...}` şeklini varsaymıştı, ama admin_panel.py'nin TÜM mevcut route'ları (`/api/service/<action>`, grup/blacklist silme) `{"ok": true/false, ...}` alanını kullanıyor. Tutarlılık için `success` yerine `ok` kullanılacak — atdd.md'nin Davranış Sözleşmesi tablosundaki `success` alanları `ok` olarak okunmalı (aynı anlam, proje konvansiyonuna uyum).
2. **Onay dialogu**: atdd.md'nin varsaydığı gibi, mevcut `if(!confirm('...'))return;` deseni (JS, backend'de ayrı bir "çift onay" mekanizması YOK) — plan.md'de doğrulandı, atdd.md'nin varsayımı doğru çıktı.
3. **Dosya silme yardımcı fonksiyonu**: Projede hazır bir "klasör sil" yardımcı fonksiyonu yok, doğrudan `shutil.rmtree` kullanılacak (yeni bir soyutlama eklenmez, CAVEMAN ilkesine uygun).

## Risks
(atdd.md'den taşındı, ek bulgu yok)
- `pm2 restart mavi-baileys-bridge` komutu bridge PM2'de kayıtlı değilse başarısız olur — `_pm2()` zaten `(False, hata_metni)` döndürüyor, bu AC-5/AC-4 davranış sözleşmesiyle doğrudan uyumlu, ek bir önlem gerekmiyor.
- Confirm dialog sadece frontend'de — kabul edilmiş bir risk (atdd.md'de not düşülmüş, tek-operatör panel).

## Open Questions
Yok — kod keşfi atdd.md'nin tüm varsayımlarını doğruladı (response şekli hariç, o da yukarıda "Kararlar" ile netleştirildi, ek claude-omni/Haiku dispatch'ine gerek yok).
