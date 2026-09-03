# Test Diff — gruplar-tab-ui-yenileme
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
| Dosya | Framework | Çalıştırma |
|---|---|---|
| `tests/test_gruplar_tab_ui.py` | pytest, `admin_panel.INDEX_HTML` üzerinde string/regex içerik testleri | `python -m pytest tests/test_gruplar_tab_ui.py -v` → **9/12 failed** (gerçek — implementasyon henüz yok), 3/12 zaten PASS (mevcut kodun sağladığı regresyon garantileri) |

## Kapsam Notu — E2E testleri burada YAZILMADI, bilinçli karar
atdd.md'nin Test Strategy'si E2E ağırlıklı (%70) belirtiyor, ama bu proje
committed Playwright test dosyası convention'ı kullanmıyor — gerçek görsel/
etkileşim doğrulaması `verify` adımında CANLI Playwright MCP ile yapılacak
(bu oturumdaki önceki UI görevlerinde de aynı desen izlendi). Bu red-step
sadece STRUCTURAL (INDEX_HTML string içeriği) testler üretti — AC-6/7
(arama sonucu boş empty-state, JS hata toleransı) client-side runtime
davranışı olduğu için buraya değil, `verify`'ın canlı Playwright turuna
bırakıldı.

## AC → Test Eşlemesi
| AC | Davranış | Test Fonksiyonu |
|---|---|---|
| AC-1 | İki panel yan yana grid | `test_two_panels_structure` |
| AC-2 | Yeni `.grp-row` sınıfı, `.bl-item` kullanılmıyor | `test_grp_row_class_exists`, `test_loadGroups_uses_grp_row`, `test_loadBaileysGroups_uses_grp_row`, `test_baileysGrpAdd_uses_grp_row` |
| AC-3 | Arama input + filtre fonksiyonu | `test_search_input_exists`, `test_filterGroups_function_exists` |
| AC-4 | `d.message` sözleşmesi korunuyor (regresyon) | `test_loadBaileysGroups_preserves_message_contract` (zaten PASS) |
| AC-5 | Yenile butonlarının onclick çağrıları korunuyor (regresyon) | `test_yenile_buttons_oncick_calls_preserved` |
| AC-6/7 | Arama boş sonuç + JS hata toleransı | N/A — canlı Playwright'a (`verify`) bırakıldı, docstring'de not düşüldü |
| Regresyon (plan.md riski) | `grpDel()` artık `.grp-row` selector kullanıyor | `test_grpDel_uses_new_row_selector` |
| Regresyon | `.bl-item` CSS tanımı hâlâ var (diğer sekmeler) | `test_bl_item_class_still_defined` (zaten PASS) |
| Regresyon | CSS değişkenleri korunuyor | `test_css_variables_preserved` (zaten PASS) |

## code-copilot İçin Bağlayıcı Varsayımlar
- Yeni satır CSS sınıfı ismi `grp-row`/`grp-item` deseniyle eşleşmeli
  (regex: `\.grp[-_](row|item)`) — tam isim code-copilot'a bırakıldı.
- Arama filtre fonksiyonu `filterGroups`/`searchGroups` deseniyle
  eşleşmeli (regex: `function\s+(filter|search)Groups?\s*\(`).
- `grpDel()` içindeki `.closest('.bl-item')` → `.closest('.grp-row')` (veya
  seçilen isim) olarak güncellenmeli — plan.md'nin bulduğu regresyon riski.
- `.bl-item` CSS TANIMI ve `--acc`/`--bg`/`--ok`/`--err` CSS değişkenleri
  SİLİNMEMELİ.
