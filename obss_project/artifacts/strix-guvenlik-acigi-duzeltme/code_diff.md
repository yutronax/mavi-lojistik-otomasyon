# Code Diff — strix-guvenlik-acigi-duzeltme (Green Step)
_Reference: atdd.md, plan.md, test_diff.md_

## Değiştirilen Dosyalar
- `src/api/webhook_server.py` (+`import secrets`, `do_POST` yeniden sıralandı — auth/şekil kontrolü 200'den önce)
- `src/api/admin_panel.py` (`_renderShipList`: `data-mid` + `escapeHtml` + `this.dataset.mid` deseni; ölü `midE` satırı temizlendi)
- `.env.example` (`WEBHOOK_SHARED_SECRET=secret_buraya` örnek satırı eklendi)

## AC Karşılanması
| AC | Nasıl karşılandı |
|---|---|
| AC-1 | Bulk butonlar ve edit butonu artık `data-mid="${escapeHtml(mid)}"` / `data-mid="${escapeHtml(encodeURIComponent(mid))}"` + `onclick="...(this.dataset.mid)"` kullanıyor, ham `${mid}`/`${midE}` interpolasyonu kalmadı |
| AC-2 | `os.getenv("WEBHOOK_SHARED_SECRET")` + `self.headers.get("X-Webhook-Secret")` + `secrets.compare_digest` — eşleşmezse 403, kuyruğa hiçbir şey eklenmiyor |
| AC-3 | Secret ortam değişkeni boşsa `not webhook_secret` koşulu 403'e düşüyor — sunucu ayakta kalıyor, sadece istek reddediliyor |
| AC-4 | `/baileys-webhook` için `messages` listesi/`id`'li obje, default path için `dict` şekil kontrolü — uymuyorsa 400, kuyruğa eklenmiyor |
| AC-5 | Secret+şekil geçerliyse 200 + mevcut `threading.Thread` ile işleme (davranış korundu) |
| AC-6 | `escapeHtml` zaten HTML özel karakterleri kaçırıyor, reddetme yok — sadece görüntüleme güvenli hale geldi |
| AC-7 (opsiyonel) | **Uygulanmadı — geri alındı.** İlk denemede `/` route'una `Content-Security-Policy: script-src 'self'` eklendi ama bu, panelin onlarca mevcut satır-içi `onclick` handler'ını (giriş, tab geçişleri, servis kontrolleri dahil) tarayıcıda bloklayıp TÜM paneli işlevsiz bırakacaktı — kritik bir regresyon. Review'da yakalanıp geri alındı. AC-7 zaten Medium/opsiyonel işaretliydi; düzgün uygulamak (tüm onclick'leri addEventListener'a taşımak) bu görevin kapsamı dışında büyük bir refactor gerektiriyor. |

## Review Sürecinde Bulunan ve Düzeltilen Sorun
İlk implementasyon denemesi AC-7'yi (opsiyonel CSP header) `'unsafe-inline'` istisnası olmadan ekledi — bu, gerçek admin panelinin tamamen bozulmasına yol açacak bir regresyondu (plan.md'nin tam olarak öngördüğü risk: "riskliyse ATLA"). İkinci bir Haiku alt-ajan dispatch'iyle sadece bu satır geri alındı, XSS düzeltmeleri (AC-1/6) dokunulmadan kaldı.

## Doğrulama
- `git status --short tests/` → test dosyaları dokunulmadı (untracked, değişmemiş).
- `git diff --stat` → sadece `admin_panel.py` (7 satır), `webhook_server.py` (100 satır), `.env.example` (1 satır) — implementasyon kapsamıyla tutarlı.
- Testler henüz ÇALIŞTIRILMADI — bu `verify` adımının işi.

## Kalan Sınırlamalar
- AC-7 (CSP) uygulanmadı, atdd.md/plan.md'de zaten opsiyonel olarak işaretliydi.
- Sidecar/Whapi header güncellemesi bu görevin kapsamı dışında (atdd.md Kapsam Dışı) — production'a bu haliyle deploy edilirse gerçek webhook trafiği 403 alabilir, kullanıcıya ayrıca hatırlatılmalı.

## Varsayımlar
- `secrets.compare_digest` kullanıldı (plan.md'nin tutarlılık kararına uygun, `hmac.compare_digest` değil).
- Test secret değeri `.env`'deki gerçek `WEBHOOK_SHARED_SECRET` ile ilgisiz, sadece test ortamı için.
