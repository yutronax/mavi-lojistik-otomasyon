# Test Diff — gruplar-tab-iyilestirme-v2
_Reference: atdd.md, plan.md_

## Genişletilen Dosyalar
| Dosya | Çalıştırma |
|---|---|
| `sidecar/test_baileys_groups_state.js` | `node sidecar/test_baileys_groups_state.js` → **exit code 1** (gerçek — 5 yeni test, hepsi kırmızı, fallback isim mantığı henüz yok) |
| `tests/test_gruplar_tab_ui.py` | `python -m pytest tests/test_gruplar_tab_ui.py -v` → **3 failed** (gerçek — pagination henüz yok), 14 passed (11 eski regresyon testi + 2 yeni test implementasyon öncesi de geçiyor, aşağıda not düşüldü) |

## Bilinen Sınırlama (blocking değil, red-team'e iletiliyor)
İki yeni test, implementasyon YOKKEN bile PASS ediyor:
- `TestVisualEnhancements::test_grp_row_styling_enhanced` (AC-4): gevşek bir
  eşik kontrolü (`.grp-row` CSS bloğunda minimum property sayısı) olduğu
  için önceki görevden kalma mevcut CSS'i zaten karşılıyor — code-copilot
  hiçbir görsel iyileştirme yapmasa bile bu test teorik olarak yeşil
  kalabilir. AC-4'ün gerçek kanıtı `verify` adımındaki `vision-test`
  (canlı görsel karşılaştırma) ile gelecek.
- `TestBaileysGroupsPaginationNegative::test_baileys_panel_no_pagination_reference`
  (AC-6): doğası gereği negatif bir test (pagination YOK olduğunu
  doğruluyor) — implementasyon öncesi de sonrası da (doğru yapılırsa)
  yeşil kalması BEKLENEN davranış, bu bir zayıflık değil.

## AC → Test Eşlemesi
| AC | Davranış | Test |
|---|---|---|
| AC-1 | subject boş/undefined/whitespace → fallback isim "İsimsiz Grup (…125432)" | `testFallbackNameForEmptySubject`, `testFallbackNameForUndefinedSubject`, `testFallbackNameForWhitespaceSubject`, `testNormalSubjectPreserved` (regresyon) |
| AC-2 | Pagination fonksiyonu + UI konteyneri | `test_pagination_function_exists`, `test_pagination_container_exists` |
| AC-3 | Arama sayfa 1'e sıfırlanır | `test_filterGroups_resets_pagination` |
| AC-4 | Görsel zenginleştirme (mevcut CSS sistemi korunarak) | `test_grp_row_styling_enhanced` (bkz. Bilinen Sınırlama — gerçek kanıt `vision-test`'te) |
| AC-5 | Baileys panelinde de fallback isim (tek veri kaynağından otomatik) | `testMixedNamedAndUnnamedGroups` |
| AC-6 | Baileys paneli pagination'dan etkilenmez | `test_baileys_panel_no_pagination_reference` |

## code-copilot İçin Bağlayıcı Varsayımlar
- **Fallback isim formatı (KESİN):** `"İsimsiz Grup (…" + g.id.split('@')[0].slice(-6) + ")"`
  — testler bu tam formatı doğruluyor, değiştirilemez.
- Pagination fonksiyon/element isimlendirmesi ESNEK — testler regex ile
  "pagina"/"sayfa" kelimesi geçen isimleri kabul ediyor.
- `filterGroups()`'un gövdesinde bir `currentPage`/`page`/`sayfa` sıfırlama
  ataması VEYA pagination fonksiyonuna bir çağrı bulunmalı.
