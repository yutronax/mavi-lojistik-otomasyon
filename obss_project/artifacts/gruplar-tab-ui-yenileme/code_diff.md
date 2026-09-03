# Code Diff — gruplar-tab-ui-yenileme
_Reference: atdd.md, plan.md, test_diff.md_

## Değiştirilen Dosyalar
| Dosya | Değişiklik |
|---|---|
| `src/api/admin_panel.py` | `#tab-grp` bölümü yeniden düzenlendi: tek `.card` içinde arama input'u (`#grp-search`) + iki panelli `.grp-grid` (masaüstü 2 kolon, mobil 1 kolon — `@media (max-width:768px)` override'ı ile). Yeni `.grp-row` CSS sınıfı (`.bl-item` SİLİNMEDİ, diğer sekmeler kullanmaya devam ediyor). `loadGroups()`/`loadBaileysGroups()` artık `.grp-row` render ediyor. `grpDel()`'in `.closest()` selector'ü `.grp-row`'a güncellendi (plan.md'nin bulduğu regresyon riski). Yeni `filterGroups()` fonksiyonu (client-side, try/catch korumalı, backend'e istek atmıyor). |

## Oluşturulan Dosyalar
Yok.

## Düzeltilen Sorunlar (ilk taslakta bulundu, red-team'e gitmeden önce giderildi)
İlk Haiku taslağı grid'i satır-içi (`style="display:grid;grid-template-columns:1fr 1fr..."`)
stille eklemişti — bu, projenin zaten sahip olduğu `.split{grid-template-columns:1fr}`
mobil-override desenini (`@media (max-width:768px)` bloğu) hiç kullanmıyordu,
yani AC-1'in ("masaüstünde 2 kolon, mobilde 1 kolon") gerçek bir ihlaliydi
— her ekran boyutunda 2 kolon kalırdı. Ayrıca `#baileys-qr-section`/
`#baileys-qr-connected-msg`'e CSS'te hiç tanımlı olmayan (ölü) `class`
attribute'ları eklenmişti. İkisi de tespit edilip düzelttirildi:
- `.grp-grid` adında isimli bir CSS sınıfı eklendi (projenin `.split`
  deseniyle tutarlı), `@media` bloğuna mobil override eklendi.
- Ölü `class="baileys-qr-section"`/`class="baileys-qr-connected-msg"`
  attribute'ları kaldırıldı.

## AC Doğrulama (gerçek test çalıştırmasıyla, bağımsız doğrulandı)
```
python -c "import ast; ast.parse(...)"                → OK
python -m pytest tests/test_gruplar_tab_ui.py -v       → 12/12 passed
python -m pytest -q (tam proje suite'i)                → 148 passed, regresyon yok
```

| AC | Durum |
|---|---|
| AC-1 (2 panel, masaüstü/mobil grid) | ✅ Test + `.grp-grid` mobil override ile doğrulandı |
| AC-2 (`.grp-row`, `.bl-item` kullanılmıyor) | ✅ Test doğrulandı |
| AC-3 (client-side arama) | ✅ Test doğrulandı |
| AC-4 (backend `d.message` sözleşmesi korunuyor) | ✅ Test doğrulandı (regresyon) |
| AC-5 (Yenile butonları aynı çağrılar) | ✅ Test doğrulandı (regresyon) |
| AC-6/7 (arama boş sonuç, JS hata toleransı) | `verify` adımındaki canlı Playwright turuna bırakıldı (test_diff.md'de belirtilmişti) |
| Regresyon (`grpDel` selector) | ✅ Test doğrulandı |
| Regresyon (`.bl-item` silinmedi, CSS değişkenleri korundu) | ✅ Test doğrulandı |

## CAVEMAN Self-Review
- Yeni dosya: yok.
- Yeni soyutlama: `filterGroups()` — atdd.md'nin AC-3'ünün gerektirdiği tek
  yeni fonksiyon, gereksiz yardımcı eklenmedi.
- Kapsam dışı hiçbir şey eklenmedi — "grup üye sayısı" gibi v0 mock
  verisindeki alanlar eklenmedi, backend'e dokunulmadı, diğer sekmeler
  değişmedi.

## Görsel UI Notu
Bu görev rendered bir web UI dosyasına (`admin_panel.py`'nin `INDEX_HTML`
HTML/CSS/JS'i) dokunuyor — `verify` adımında gate 12'nin (`vision-test`)
N/A DEĞİL, aktif çalışması gerekiyor (atdd.md'de zaten belirtilmişti).
