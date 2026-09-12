# Plan — web-admin-panel-ayarlar-temizlik-tasarim
_Reference: atdd.md_

Frontend-pipeline: tetikleyici eşleşti (atdd.md "Görsel/UI kriteri" dolu, gerçek bir web sayfası — Flet'in aksine bu kez uygulanabilir). Discover adımı çalıştırıldı (aşağıda). Design Direction adımı atlandı — skill'in kendi kuralı gereği ("sadece mevcut bir bug/polish fix'inde bu adımı atla"), bu görev yeni UI/kapsamlı reshape değil, küçük ölçekli temizlik+polish.

## Discover (Playwright/Browser, frontend-pipeline adım 1)
`INDEX_HTML` (admin_panel.py içinden regex ile çıkarıldı) statik bir HTTP sunucusunda (scratchpad, proje dışı — backend'e/gerçek verilere dokunulmadan) açıldı, login/app toggle JS'i manuel tetiklenip Ayarlar sekmesi (`tab-set`) sahte verilerle render edildi. Sonuç, kullanıcının paylaştığı ekran görüntüsüyle birebir eşleşti (`FETCH_HOURS_BACK`, `DUPLICATE_CHECK_HOURS`, ... ham key isimleriyle).

Tespit edilen gerçek tasarım token'ları (satır 10, `:root`):
```
--bg:#f7f7f8 --card:#fff --acc:#f39c12 --acc-dark:#d9840a --acc-soft:#fff2e0
--ok:#16a34a --warn:#f39c12 --err:#dc2626 --tx:#1f2937 --mut:#6b7280 --border:#e5e7eb
```
Kart: `border-radius:14px`, input: `border-radius:10px;padding:12px`. **Hiçbir input'ta focus stili yok** (satır aralığında grep — 0 sonuç, sadece Ayarlar'da değil, tüm panelde). Global `input`/`label`/`.card` kuralları diğer tüm sekmeler (mesajlar, kara liste, loglar) tarafından paylaşılıyor — bunlara dokunmak scope creep + tutarlılık riski (atdd.md Risks).

## Audit
Tam `better-interface` taraması bu kapsam için orantısız (12→10 alan azaltma + tek bölümün stil zenginleştirmesi). Hafif/kapsam-sınırlı gözlem: grup başlıkları (`SİSTEM AYARLARI`/`AI API ANAHTARLARI`) düz metin, görsel ayraç yok; input'larda odaklanma (focus) geri bildirimi yok (erişilebilirlik açısından da eksik — klavye kullanıcısı hangi alanda olduğunu göremiyor). Bu ikisi bu görevin "Tasarım Yönü" kapsamına zaten giriyor (atdd.md).

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | AC-1/AC-2/AC-S1: `EDITABLE_ENV_KEYS` listesinden (satır 67-80) `START_HOUR`/`END_HOUR` çıkarılacak. AC-5/Tasarım Yönü: `INDEX_HTML` içinde `loadSet()`'in ürettiği grup başlığı markup'ına (satır ~2065-2069) hafif stil (ikon/ayraç), ve YENİ, Ayarlar'a ÖZEL scoped CSS kuralları (`#set-fields input:focus{...}` gibi — global `input:focus` DEĞİL) eklenecek. | low |

## New Files
Yok.

## Dependencies
- `EDITABLE_ENV_KEYS` listesi → `settings_get`/`settings_save` route'larının (satır 1119-1170) filtre mantığı zaten bu listeyi kullanıyor, değişmeyecek (sadece liste küçülüyor).
- `loadSet()`/`saveSet()` JS (satır 2057-2085) → dinamik render, `d.editable` listesine bağlı, kod değişikliği gerektirmiyor (liste küçülünce otomatik uyum sağlıyor); sadece CSS/markup zenginleştirmesi eklenecek.
- Global CSS (`:root`, `.card`, `input`, `label` — satır 10-65) → SADECE REFERANS, değiştirilmeyecek (diğer sekmelerle paylaşılıyor).

## Migration Required?
Hayır. `.env` şeması değişmiyor (AC-4: eski `START_HOUR`/`END_HOUR` satırlarına dokunulmuyor, sadece `EDITABLE_ENV_KEYS`'ten çıkarılıyor).

## Risks
- Scoped CSS eklerken yanlışlıkla global bir seçici (`input:focus` gibi) yazılırsa diğer sekmelerin görünümü kazara değişir — code-copilot'a `#set-fields` veya `#tab-set` scope'u açıkça verilecek.
- `EDITABLE_ENV_KEYS`'ten bir anahtar çıkarmak hem GET (görünürlük) hem POST (yazılabilirlik) filtresini aynı anda etkiliyor — bu istenen davranış (AC-S1), ama code-copilot'un `settings_get`/`settings_save`'i AYRI AYRI değiştirmediğini (tek listeye dokunduğunu) doğrulamak gerek.

## Open Questions
Yok — Discover ile tasarım token'ları netleşti, atdd.md'nin "Tasarım Yönü" bölümü zaten somut. Sonnet 5 alt-ajanına dispatch gerekmedi.
