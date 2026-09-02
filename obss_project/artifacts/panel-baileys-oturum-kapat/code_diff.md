# Code Diff — panel-baileys-oturum-kapat
_Reference: atdd.md, plan.md, test_diff.md_

## Değiştirilen Dosya
`src/api/admin_panel.py`:
- Satır 50: `BAILEYS_AUTH_DIR = os.path.join(PROJECT_ROOT, "sidecar", "auth_info_baileys")` sabiti eklendi.
- Satır 292-326: yeni route `POST /api/whatsapp/disconnect` (`@require_auth`) — dosya silme → pm2 restart sırasıyla, AC-1..AC-5'in tamamını karşılayan davranış.
- Satır 1264: "🔌 Bağlantıyı Kes" butonu (`confirm(...)` onaylı, mevcut `deleteMsg()` deseniyle birebir).
- Satır 1592-1602: `async function disconnectBaileys()` — mevcut `api()`/`toast()` yardımcı fonksiyonlarını kullanıyor, sonucu `checkBaileysQr()` çağrısıyla UI'ya yansıtıyor.

## Oluşturulan Dosya
Yok.

## AC Doğrulama (gerçek test çalıştırmasıyla + canlı tarayıcı)
```
pytest tests/test_baileys_disconnect_panel.py -v   → 18 passed
pytest -q (tüm proje)                              → 90 passed (72 önceki + 18 yeni, regresyon yok)
```

| AC | Durum |
|---|---|
| AC-1 (happy path) | ✅ `test_disconnect_happy_path_with_real_directory`, `_response_structure` |
| AC-2 (idempotent) | ✅ `test_disconnect_idempotent_directory_not_found`, `_error_message_not_shown` |
| AC-3 (401) | ✅ 4 test (token yok/geçersiz/süresi dolmuş/malformed) |
| AC-4 (dosya silme hatası) | ✅ 3 test, `_pm2` hiç çağrılmadığı doğrulanıyor |
| AC-5 (kısmi başarı) | ✅ 3 test, `file_deleted:true` alanı doğrulanıyor, "self-healing" retry senaryosu |
| AC-6 (confirm dialog) | ✅ Canlı Playwright testinde DOĞRULANDI — buton tıklanınca gerçek `confirm("WhatsApp bağlantısı kesilsin mi?...")` dialogu tetiklendi, onaylanınca gerçek `POST /api/whatsapp/disconnect` isteği gitti, hata toast'ı (`step` alanı dahil) doğru göründü |

## Canlı Doğrulama Notu
Panel-baileys-qr-gosterimi görevinde (önceki task) statik incelemenin kaçırdığı bir JS-string-kaçış hatası canlı testte bulunmuştu — bu derse istinaden bu görevde de yerel sunucu başlatılıp gerçek tarayıcıda (Playwright) buton tıklanarak confirm dialogu ve gerçek API çağrısı uçtan uca doğrulandı. Konsol hatası yok (sadece zararsız favicon 404). Yerel ortamda `pm2` komutu kayıtlı olmadığı için beklenen 500/pm2_restart hatası alındı — bu implementasyon hatası DEĞİL, AC-5/hata-yolu davranışının doğru çalıştığının kanıtı.

## CAVEMAN Self-Review
- Yeni dosya: yok.
- Yeni soyutlama/yardımcı fonksiyon: yok — doğrudan `shutil.rmtree` (stdlib) ve mevcut `_pm2()` kullanıldı.
- Kapsam dışı hiçbir şey eklenmedi (otomatik yeniden bağlanma, çoklu hesap, audit log — hepsi atdd.md'nin "Kapsam Dışı"nda, hiçbiri implementasyona sızmadı).
- Mevcut proje desenleri (response `{"ok":...}`, `require_auth`, `_pm2()`, `confirm()`/`toast()`/`api()`) birebir takip edildi.
