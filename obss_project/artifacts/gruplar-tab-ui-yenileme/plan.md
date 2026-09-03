# Plan — gruplar-tab-ui-yenileme
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `src/api/admin_panel.py` | AC-1..7: `INDEX_HTML` string sabiti içindeki 3 bölüm değişecek: (1) `#tab-grp` div'i (satır 1212-1233) — iki panelli grid, arama kutusu, yeni empty-state markup'ı eklenecek; (2) CSS bloğu (satır ~1019-1070 civarı) — `.bl-item`/`.card`/`.b-ok`/`.b-err` DOKUNULMADAN, yeni `.grp-*` sınıfları eklenecek; (3) JS fonksiyonları (satır 1542-1602 civarı) — `loadGroups()` (1548), `loadBaileysGroups()` (1555), `baileysGrpAdd()` (1581), `grpDel()` (1591) render mantığı `.bl-item` yerine yeni `.grp-row` markup'ı üretecek şekilde güncellenecek, YENİ bir `filterGroups()` fonksiyonu + arama input event listener eklenecek. `checkBaileysQr()`/`disconnectBaileys()` (1501-1540) İÇERİK olarak DEĞİŞMEYECEK (AC kapsamı dışı), sadece varsa çevresindeki HTML wrapper'ı yeni layout'a uyacak şekilde taşınabilir. | medium — tek dosyada 3 farklı bölüm, dikkatli izolasyon gerekiyor |

## New Files
Yok — `verify` adımında yeni bir Playwright test dosyası gerekebilir (`test-copilot` karar verecek), ama bu implementasyon dosyası değil.

**Not (vision-test tetikleyicisi):** `src/api/admin_panel.py`'nin `INDEX_HTML` sabiti gerçek rendered bir web UI'dır (HTML/CSS/JS) — bu görev `verify` adımında gate 11'in (`vision-test`) N/A DEĞİL, aktif çalışması gerektiği anlamına gelir (atdd.md'de zaten belirtilmişti, burada teyit ediliyor).

## Dependencies
- Mevcut yardımcı fonksiyonlar (DEĞİŞMEYECEK, yeniden kullanılacak):
  `api()` (fetch wrapper), `$()` (getElementById kısayolu), `escapeHtml()`,
  `toast()`, `_grpFlash()` (satır 1587 civarı, ekleme sonrası flash efekti).
- Mevcut API sözleşmeleri (DEĞİŞMEYECEK):
  - `GET /api/groups` → `{groups: [{id, name}]}`
  - `GET /api/whatsapp/groups` → başarı: `{groups: [{id, name, saved}]}`,
    202/boş durum: `{message: "..."}` (satır 1561'de `if(d.message)` ile
    ayrıştırılıyor — bu KOŞUL YAPISI korunmalı, AC-4'ün empty-state'i bu
    `d.message` değerini kullanacak).
  - `POST /api/groups` (ekleme) → `{ok: true}` veya `{error/msg}`
  - `DELETE /api/groups/<id>` (silme, `grpDel()` içinde)
- `checkBaileysQr()`'ın kullandığı `#baileys-qr-section`,
  `#baileys-qr-connected-msg`, `#baileys-disconnect-btn` ID'leri — bu
  görev bu ID'leri KORUMALI (JS fonksiyonu değişmiyor), sadece görsel
  konumlandırması yeni layout'a (örn. panellerin üstünde bir bağlantı
  kartı) taşınabilir.

## Migration Required?
Hayır — hiçbir DB/schema değişikliği yok, düz HTML/CSS/JS string değişikliği.

## Risks
- (atdd.md'den) Tek dosyaya gömülü olmak — code-copilot'un SADECE
  `#tab-grp` ve ilgili 3 bölümü (yukarıda satır numaralarıyla belirtildi)
  değiştirmesi, dosyanın geri kalanına (diğer sekmeler, `loadSent()`,
  `loadBl()` vb.) dokunmaması gerekiyor. Plan bu riski satır numaralarıyla
  daraltarak azaltıyor.
- (atdd.md'den) v0 mock verisindeki "üye sayısı" gibi gerçek API'nin
  sağlamadığı alanlar — code-copilot'a AÇIKÇA "bu alanı ekleme" talimatı
  verilecek.
- **YENİ:** `grpDel()` fonksiyonu şu an `event.target.closest('.bl-item')`
  kullanıyor (satır 1592) — DOM yapısı `.grp-row`'a değişince bu selector
  da `.grp-row`'a güncellenmeli, aksi halde silme onayı diyaloğunda grup
  adı boş/yanlış görünür (sessiz bir regresyon riski, code-copilot'a
  açıkça iletilecek).

## Open Questions
Yok — atdd.md'nin Sorular ve Cevaplar bölümü + yukarıdaki kod keşfi
(fonksiyon/CSS/satır numaraları, `grpDel()`'in selector bağımlılığı)
implementasyon için yeterli netlikte. code-copilot'a iletilecek tek ek
talimat: `grpDel()`'deki `.closest('.bl-item')` selector'ünü yeni satır
sınıfına güncellemek.
