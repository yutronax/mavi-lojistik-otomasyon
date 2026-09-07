# Plan — baileys-groups-pagination
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | (1) `#baileys-available-groups-list`'in bulunduğu HTML bölümüne (satır ~1240-1246) yeni bir `#baileys-pagination` section eklenecek. (2) Gruplar'daki `currentPage`/`grpSearchMatches`/`ITEMS_PER_PAGE` tanımlarının yanına (satır ~1293-1296 civarı) `baileysCurrentPage` VE `baileysSearchMatches` eklenecek (aşağıdaki "Dependencies" bölümündeki kritik bulguya bakınız — Baileys'in de Gruplar gibi bir arama-eşleşme state'ine ihtiyacı var, Kara Liste'nin aksine). (3) `loadBaileysGroups()`'un HER üç dönüş noktasında (`d.message` erken dönüşü, `!unsaved.length` erken dönüşü, ve normal akış sonu) pagination state'i sıfırlanıp yeniden render edilmeli. (4) Yeni `renderBaileysGrpPagination(page)` fonksiyonu, `renderGrpPagination`'ın izole kopyası olarak eklenecek. (5) `filterGroups()`'un Baileys tarafı (satır ~1690-1699) YENİDEN YAZILMALI — şu an doğrudan `row.style.display = match?'':'none'` yapıyor, bu pagination ile ÇAKIŞIR (bkz. Dependencies). | medium |

Bu görev, rendered bir web UI dosyasına dokunuyor — `verify` adımında gate 11/12 (`vision-test`) N/A değil **aktif** çalışmalı.

## New Files
Yok — mevcut tek-dosya gömülü desen korunuyor.

## Dependencies (kritik bulgu — atdd.md'nin varsayımını düzeltiyor)
`filterGroups()` (satır 1676-1705) okundu. Kayıtlı Gruplar ve Kara Liste'den FARKLI bir üçüncü arama deseni ortaya çıktı:

- **Kayıtlı Gruplar:** `filterGroups()` eşleşen satırları bir DİZİYE (`matched`) toplar, `grpSearchMatches = query ? matched : null` ile saklar, `renderGrpPagination` bu diziyi (`grpSearchMatches !== null ? grpSearchMatches : Array.from(allRows)`) "arama sonrası görünür küme" olarak kullanıp İÇİNDE sayfalar.
- **Kara Liste:** Arama server-side (`loadBl()` her tuşta sunucudan yeniden çeker), `#bl-list` her zaman zaten filtrelenmiş tam kümeyi içerir — ayrı bir eşleşme-state'ine gerek yok.
- **Baileys Grupları (ŞU AN):** `filterGroups()`'un Baileys kısmı DOĞRUDAN `row.style.display = match ? '' : 'none'` yapıyor — yani arama, DOM'daki `display` özelliğini pagination'dan BAĞIMSIZ olarak elle kontrol ediyor. Pagination eklenirse, `renderBaileysGrpPagination`'ın "sayfa aralığına göre gizle/göster" mantığı ile `filterGroups()`'un "eşleşmeyeni gizle" mantığı ÇAKIŞIR (ikisi de aynı `row.style.display`'i farklı zamanlarda ezer, sonuç kararsız olur — örn. arama eşleşmeyen bir satır, sayfa hesaplamasında hâlâ "görünür" sayılabilir).

**Sonuç: Baileys için Kayıtlı Gruplar'ın deseni (arama-eşleşme dizisi + üzerinde sayfalama) izole bir kopyası olarak uygulanmalı** — `baileysSearchMatches` (Gruplar'ın `grpSearchMatches`'inin izole kopyası), `filterGroups()`'un Baileys bloğu artık doğrudan `display` set etmek yerine eşleşenleri bir diziye toplayıp `baileysSearchMatches`'e yazacak ve `baileysCurrentPage = 1; renderBaileysGrpPagination(1);` çağıracak. Bu, atdd.md'nin "sadece pagination katmanı ekleniyor, filterGroups mantığı değişmeyecek" varsayımıyla (Kapsam Dışı bölümü) kısmen çelişiyor — filterGroups'un Baileys bloğu değişmek ZORUNDA, ama filtreleme SONUCU (hangi satırın eşleştiği) aynı kalıyor, sadece "eşleşeni nasıl gösterdiği" mekanizması değişiyor. Bu bir Open Question olarak aşağıda işaretlendi.

## Migration Required?
Hayır.

## Risks
- (atdd.md'den taşındı) `filterGroups()` HER İKİ listeyi aynı anda işlediği için, Baileys bloğunu değiştirirken Kayıtlı Gruplar bloğuna (satır 1678-1688) yanlışlıkla dokunma riski var — sadece Baileys bloğu (satır 1690-1699) değiştirilmeli, `regRows`/`grpSearchMatches`/`currentPage` mantığı AYNEN kalmalı.
- **Yeni risk:** `loadBaileysGroups()`'un iki erken-dönüş noktası (`d.message`, `!unsaved.length`) şu an pagination'ı hiç sıfırlamıyor/gizlemiyor — eğer önceki bir yüklemede pagination görünür haldeyken kullanıcı yenile'ye basar ve bu sefer 0 sonuç dönerse, eski pagination HTML'i EKRANDA KALABİLİR (stale UI). Bu üç dönüş noktasının HEPSİNDE `baileysCurrentPage = 1;` + pagination'ı gizleme/yeniden render etme çağrısı olmalı — plan.md'nin "Files to Modify" satırı bunu madde (3) olarak işaretledi.

## Open Questions (Kararlar)
1. **Çözüldü (Read ile doğrulandı, alt-ajana gerek kalmadı):** `filterGroups()`'un Baileys bloğu, atdd.md'nin varsaydığından farklı olarak DEĞİŞMEK ZORUNDA (yukarıdaki Dependencies bulgusu) — doğrudan `display` set etmek yerine `baileysSearchMatches` dizisine yazıp `renderBaileysGrpPagination(1)` çağıracak şekilde yeniden yazılacak. Filtrelemenin SONUCU (hangi grup adı eşleşiyor) değişmiyor, sadece görüntüleme mekanizması pagination'la uyumlu hale getiriliyor. Bu, code-copilot'a doğrudan aktarılacak.
