# Plan — strix-guvenlik-acigi-duzeltme
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `src/api/admin_panel.py` | AC-1/6/7: `_renderShipList`'te (satır 1598-1622) `mid`/`midE` ham interpolasyonunu `data-mid` attribute + `escapeHtml`'e taşımak; `openEditModal('${midE}',...)` çağrısını `this.dataset.mid` okuyacak şekilde güncellemek; mevcut `escapeHtml` (satır 1541-1543) fonksiyonu zaten var, yeniden kullanılacak. Opsiyonel CSP header (AC-7) için Flask response'a `Content-Security-Policy: script-src 'self'` eklenecek — bu response header'ları döndüren route'un bulunması gerekiyor (muhtemelen ana `/` route'u, keşif code-copilot aşamasında). | medium — inline `onclick` çağrı imzaları değişiyor, `approveAll`/`deleteMsg`/`openEditModal` JS fonksiyonlarının parametre kaynağı değişiyor, tüm çağrı noktaları tutarlı güncellenmeli |
| `src/api/webhook_server.py` | AC-2/3/4/5: `do_POST` (satır 114-153) şu an body'yi parse eder etmez, hiçbir doğrulama yapmadan 200 döner (satır 121-125), SONRA işler. Bunu tersine çevirip önce `X-Webhook-Secret` header'ını `secrets.compare_digest` ile karşılaştırmak (proje zaten `admin_panel.py:164`'te aynı deseni kullanıyor — `secrets.compare_digest`, `hmac.compare_digest` değil, tutarlılık için bu izlenmeli), secret tanımsızsa/yanlışsa 200'den ÖNCE 403 dönmek, JSON şeklini (`messages` listesi ya da tekil obje) doğrulayıp uymuyorsa 400 dönmek gerekiyor. | high — mevcut "önce 200 dön, sonra işle" akışı webhook timeout'unu önlemek için bilinçli tasarlanmış (satır 121 yorumu: "prevent webhook timeout drops"); auth kontrolü 200'den önce eklenince olası ekstra gecikme veya orkestrasyon sırası riski var, dikkatli sıralama gerekiyor |

## New Files
Yok — `WEBHOOK_SHARED_SECRET` değeri `.env`'e eklenecek (bkz. Dependencies) ama bu bir kod dosyası değil, code-copilot'un yazacağı bir "yeni dosya" değil.

## Dependencies
- `src/api/admin_panel.py:122` — `require_auth` decorator ve `admin_panel.py:164` — `secrets.compare_digest(str(body.get("password", "")), pwd)` deseni: webhook secret karşılaştırması bu projenin zaten kullandığı `secrets.compare_digest` çağrısıyla tutarlı olmalı (ATDD'nin önerdiği `hmac.compare_digest` yerine, aynı standart kütüphane fonksiyonunun aynı etkiye sahip bu projedeki mevcut varyantı).
- `.env.example` (kök dizin) — yeni `WEBHOOK_SHARED_SECRET=` satırı örnek olarak eklenmeli (gerçek değer `.env`'e, kullanıcı tarafından üretilip girilecek — bkz. atdd.md Assumptions, code-copilot bu değeri üretmemeli/yazmamalı, sadece okuma kodunu yazmalı).
- `webhook_server.py:167` — `make_webhook_handler_class(target_orchestrator)`: secret kontrolü sınıf seviyesinde (instance-bağımsız, `os.getenv` ile) eklenebilir, `target_orchestrator` mekanizmasına dokunmaya gerek yok.
- `webhook_server.py:127` — `/baileys-webhook` ve default path ayrımı korunmalı; secret kontrolü HER İKİ path için de (route ayrımından ÖNCE) uygulanmalı.

## Migration Required?
Hayır — şema/veri değişikliği yok, sadece iki dosyada davranış değişikliği ve `.env.example`'a bir örnek satır ekleniyor.

## Risks
(atdd.md'den taşındı + keşifle netleşenler)
- **Sidecar/Whapi kesintisi (atdd.md Risks'ten taşındı):** Baileys sidecar ve Whapi webhook kaydı `X-Webhook-Secret` göndermiyor; bu değişiklik tek başına deploy edilirse gerçek trafik 403 alır. **Kapsam dışı bırakıldı, code-copilot bunu YAZMAYACAK** — sadece webhook_server.py'nin kendisi düzeltilecek, sidecar/whapi tarafı ayrı görev.
- **Timing riski (keşifle bulundu):** Mevcut kod bilinçli olarak "önce 200 dön" yapıyor (satır 121 yorumu, webhook timeout'unu önlemek için). Auth kontrolünü 200'den önceye taşımak bu tasarım kararını tersine çeviriyor — `secrets.compare_digest` ve JSON şekil kontrolü mikrosaniye mertebesinde olduğu için (atdd.md AC-8) pratik bir gecikme riski yok, ama code-copilot bu sıralamayı DEĞİŞTİRMEMELİ (auth/şekil kontrolü → sonra 200/403/400), sadece kontrolü ekleyip yerleştirmeli.
- **İki path'in de korunması:** `/baileys-webhook` ve default path ayrı route'lar (satır 127); secret kontrolü ikisini de kapsamalı, sadece birini değil.

## Open Questions
Yok — atdd.md'nin Sorular ve Cevaplar bölümü + kod keşfi (mevcut `secrets.compare_digest` deseni, `require_auth` örneği, `.env.example` yapısı) planı doldurmaya yetti. Sonnet 5 alt-ajanına dispatch gerekmedi.
