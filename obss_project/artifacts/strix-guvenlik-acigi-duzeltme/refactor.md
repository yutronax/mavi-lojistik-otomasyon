# Refactor — strix-guvenlik-acigi-duzeltme
_Reference: verify_report.md (29 passed, 1 skipped, 0 failed)_

## Değerlendirilen Aday
`webhook_server.py::do_POST` içinde 4 kez tekrarlanan bir kalıp var: `self.send_response(N); self.send_header('Content-type', 'application/json'); self.end_headers(); self.wfile.write(json.dumps({...}).encode('utf-8'))` (403, 400×2, 200 blokları). Ölçülebilir tekrar (4× aynı 4 satır) — `_send_json(status, payload)` gibi küçük bir yardımcıya çıkarılabilirdi.

## Karar: Dokunulmadı
**Kasıtlı olarak atlandı**, "denendi kırdı" değil — hiç denenmedi. Gerekçe:
- Bu, commit'e hazır, testleri yeni yeşile dönmüş güvenlik-kritik bir dosya (webhook auth). Şu an ek bir düzenleme yapmak (yeni bir Haiku dispatch + yeniden test) fayda/risk oranını haklı çıkarmıyor — tekrar 4×4 satırlık küçük bir blok, okunabilirliği ciddi bozmuyor, ve her ek dokunuş `red-team`'in inceleyeceği diff'i büyütüp gözden kaçırılabilir bir hataya alan açıyor.
- `ponytail` ilkesi: varsayılan cevap "dokunma"; gerekçe sadece "daha temiz olur" ise yapılmaz. Burada ölçülebilir bir tekrar var ama görevin ölçeğine (2 dosya, ~107 satır net değişiklik) göre düşük öncelikli.
- admin_panel.py tarafında refactor adayı yok — diff zaten minimal (7 satır), `escapeHtml` gibi mevcut fonksiyon yeniden kullanıldı, yeni soyutlama yok.

## Kapsam Dışında Not Düşülen (dokunulmadı)
- `security-scan` gate'inde bulunan pre-existing bandit bulguları (B310, B104×2, B602) — bu görevin diff'i dışında, ayrı bir görev/temizlik olarak flag edilmeli (aşağıda `spawn_task` ile öneriliyor).

## Test Durumu
Değişiklik yapılmadığı için yeniden test koşumu gerekmedi — `verify_report.md`'deki 29 passed/1 skipped hâlâ geçerli.
