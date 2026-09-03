# Plan — gruplar-tab-iyilestirme-v2
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `sidecar/bridge.js` | AC-1/AC-5: `writeGroupsState()` (satır 148-164) — `name: g.subject` satırı, `g.subject` boş/undefined/whitespace-only ise fallback isim üretecek şekilde değişecek. | low |
| `src/api/admin_panel.py` | AC-2/AC-3/AC-4/AC-6: `#tab-grp` HTML/CSS'i (satır ~1213-1246 civarı) pagination kontrolü + görsel zenginleştirmeler için genişleyecek. `loadGroups()` (satır 1562) render mantığına sayfalama entegre edilecek. `filterGroups()` (satır 1618) arama sonrası sayfa 1'e dönecek şekilde güncellenecek. | medium — mevcut arama/empty-state mantığıyla (`grp-search-empty` vb., önceki görevde eklendi) entegrasyon dikkat gerektiriyor |

## New Files
Yok.

**Vision-test tetikleyicisi:** Bu görev rendered bir web UI dosyasına dokunuyor — `verify` adımında gate 12 (`vision-test`) N/A DEĞİL, aktif olmalı (atdd.md'de zaten belirtilmişti).

## Dependencies
- **KRİTİK DÜZELTME (atdd.md'nin Unknowns'ı burada çözüldü):** `writeGroupsState()`
  (satır 154) `id: g.id` kullanıyor — Baileys grup ID'leri her zaman
  `<numeric>@g.us` formatında (WhatsApp grup JID standardı, projenin başka
  yerlerinde de — örn. blacklist görevinde — aynı format doğrulanmıştı).
  `@g.us` soneki SABİT olduğu için "ID'nin son 6 karakteri" fikri (atdd.md'nin
  önerdiği) İŞE YARAMAZ — her zaman aynı "0@g.us" gibi bir şey verir, hiç
  ayırt edici olmaz. DÜZELTME: fallback isim, ID'nin `@` işaretinden ÖNCEKİ
  sayısal kısmının SON 6 hanesini kullanmalı, örn.
  `"İsimsiz Grup (…" + g.id.split('@')[0].slice(-6) + ")"`.
- Mevcut `filterGroups()` fonksiyonu (satır 1618-1645 civarı, önceki
  görevde eklendi) `.grp-row` satırlarını `style.display` ile gizleyip
  gösteriyor ve `#grp-search-empty`/`#baileys-search-empty` empty-state'lerini
  yönetiyor — pagination bu mantıkla ÇAKIŞMAMALI: bir satır hem arama
  tarafından hem pagination tarafından gizlenebilir, ikisinin birlikte
  doğru çalışması (arama eşleşen ama başka sayfada olan satırların da
  gizlenmesi, mevcut sayfanın arama sonrası sıfırlanması) code-copilot'a
  net anlatılmalı.
- `loadGroups()` (satır 1562) şu an TÜM `.grp-row` satırlarını
  `$('grp-list').innerHTML = ...` ile tek seferde yazıyor — pagination
  bunun ÜSTÜNE bir client-side görünürlük katmanı olarak eklenmeli (DOM'a
  hepsi yazılır, sadece görünürlük kontrol edilir) — CAVEMAN ilkesine
  uygun en basit yaklaşım, ayrı bir "sayfa verisi" state yönetimi
  kurmaya gerek yok.

## Migration Required?
Hayır — düz kod değişikliği.

## Risks
- (atdd.md'den, ÇÖZÜLDÜ) Fallback isim formatı — yukarıda "Dependencies"
  bölümünde düzeltildi: ID'nin `@`'den önceki kısmının son 6 hanesi.
- (atdd.md'den) Pagination + arama entegrasyonu — yukarıda netleştirildi,
  code-copilot'a hem `filterGroups()`'a hem yeni pagination fonksiyonuna
  aynı "hangi satır görünür" mantığını nasıl paylaştıracağı net
  anlatılmalı (örn. tek bir `applyGrpVisibility()` fonksiyonu, hem arama
  eşleşmesini hem sayfa aralığını kontrol eden).
- **YENİ:** `#grp-count` metni şu an `Kayıtlı ${d.groups.length} grup`
  şeklinde toplam sayıyı gösteriyor (satır 1562 civarı) — pagination
  eklenince bu metnin "Kayıtlı 100 grup (sayfa 1/5)" gibi güncellenmesi
  gerekebilir, ama atdd.md bunu net istemiyor — CAVEMAN ilkesiyle en
  basit hali (toplam sayı + ayrı bir sayfa göstergesi) tercih edilecek,
  aşırı mühendislik yapılmayacak.

## Open Questions
Yok — atdd.md'nin Unknowns'ı (fallback isim formatı) bu adımda kod
okunarak çözüldü, ayrıca soru sormaya gerek kalmadı.
