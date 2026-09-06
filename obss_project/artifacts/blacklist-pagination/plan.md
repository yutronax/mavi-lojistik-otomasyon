# Plan — blacklist-pagination
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | Kara Liste bölümüne (`#bl-list`, satır ~1264-1272) yeni bir `#bl-pagination` section eklenecek (HTML), `loadBl()` (satır ~1769-1774) sonuna `renderBlPagination(1)` çağrısı eklenecek, ve Gruplar'daki `renderGrpPagination`'ın (satır 1577-1623) izole bir kopyası olarak `renderBlPagination(page)` fonksiyonu (JS) eklenecek. Ayrıca `ITEMS_PER_PAGE`/`currentPage` global değişkenlerinin (satır 1293-1295) yanına `blCurrentPage` eklenecek — `ITEMS_PER_PAGE` (20) zaten paylaşılan bir sabit olduğu için tekrar tanımlanmayacak. | low |

Bu görev, rendered bir web UI dosyasına (gömülü HTML/JS, `admin_panel.py` içinde) dokunuyor — `verify` adımında gate 11/12 (`vision-test`) N/A değil **aktif** çalışmalı, atlanmamalı.

## New Files
Yok — mevcut tek-dosya gömülü desen korunuyor, ayrı bir `.js`/`.css`/`.html` dosyası oluşturulmayacak (CAVEMAN: projenin build-sistemsiz tek-dosya deseni bozulmayacak).

## Dependencies
- `ITEMS_PER_PAGE = 20` (satır 1294) — zaten global, kara liste için yeniden tanımlanmayacak, aynı sabit paylaşılacak.
- Gruplar'ın `.b-acc` buton class'ı ve `‹`/`›` karakterleri — pagination buton stilini birebir taklit etmek için aynı class kullanılacak, yeni CSS eklenmeyecek.
- `.bl-item` CSS class'ı (satır 1068-1069) — zaten var, satır gizleme/gösterme (`display:none`/`''`) bu class'ın elemanlarına uygulanacak (Gruplar'da `.grp-row`'a uygulandığı gibi).
- `loadBl()` (satır 1769-1774) — arama akışı zaten **server-side**: `#bl-q` input'u her değiştiğinde `/api/blacklist?q=...` sorgusu atıp `#bl-list`'i SIFIRDAN yeniden dolduruyor (Gruplar'ın client-side `filterGroups()`'undan FARKLI — o mevcut DOM satırlarını `grpSearchMatches` ile filtreliyor, tekrar sunucuya sormuyor).

## Migration Required?
Hayır — şema/veri değişikliği yok, sadece client-side render mantığı.

## Risks
- (atdd.md'den taşındı) Gruplar'ın `currentPage`/`grpSearchMatches` global değişkenleriyle isim çakışması riski — `blCurrentPage` ile ayrı isimlendirme bunu önler.
- (atdd.md'den taşındı) Bu görev tamamen manuel/e2e doğrulamaya dayanıyor, otomatik regresyon koruması zayıf.
- **Yeni bulgu:** atdd.md'nin AC-4 ve Assumptions bölümünde önerdiği `blSearchMatches` (Gruplar'daki `grpSearchMatches`'e benzer bir "eşleşen satırları hatırla" değişkeni) **gereksiz** — çünkü kara listenin arama akışı zaten server-side: her `loadBl()` çağrısı `#bl-list`'i baştan, SADECE arama sonucundaki elemanlarla dolduruyor. Yani `renderBlPagination`'ın okuyacağı `document.querySelectorAll('#bl-list .bl-item')` zaten her zaman "geçerli/filtrelenmiş" tam kümedir — ayrı bir eşleşme-takip değişkenine gerek yok. Bu, atdd.md'nin AC-4/AC-2 hedeflediği davranışı (arama sonrası sayfa 1'e dönme, doğru sayıda sayfa gösterme) DAHA BASİT şekilde karşılıyor: `renderBlPagination` sadece `#bl-list`'in o anki tüm `.bl-item` çocuklarını `allRows` olarak alıp (Gruplar'daki `grpSearchMatches !== null ? grpSearchMatches : Array.from(allRows)` şartlı mantığına hiç gerek kalmadan) direkt bunlar üzerinde sayfalar.

## Open Questions (Kararlar)
1. atdd.md'nin Assumptions bölümünde önerilen `blSearchMatches` değişkeni yukarıdaki bulgu nedeniyle implementasyonda KULLANILMAYACAK (daha basit bir çözüm var) — bu bir sapma, code-copilot'a doğrudan aktarılacak, ayrıca soru sorulmasına gerek yok (CAVEMAN: en basit çözüm zaten netleşti).
2. **Çözüldü (Read ile doğrulandı, alt-ajana gerek kalmadı):** `blDel()` (satır 1780-1784) başarılı silme sonrası HER ZAMAN `loadBl()`'ü tekrar çağırıyor — bu, listeyi sunucudan sıfırdan çekip `#bl-list`'i yeniden dolduruyor. Yani atdd.md'nin AC-5'inde tarif edilen "son sayfadaki tek kayıt silinince bir önceki sayfaya dönme" senaryosu zaten OTOMATİK olarak gerçekleşiyor — çünkü her silme sonrası `renderBlPagination(1)` çağrılacak (loadBl()'ün sonuna eklenecek), sayfa doğal olarak 1'e döner. Ayrı bir `Math.min(currentPage, totalPages)` clamp mantığına GEREK YOK; AC-5'in davranış sözleşmesi satırı basitleşiyor.
