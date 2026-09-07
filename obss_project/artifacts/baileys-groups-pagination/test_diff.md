# Test Diff — baileys-groups-pagination
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
- `tests/test_baileys_grp_pagination.py` (yeni, 16 test, Haiku alt-ajanı tarafından yazıldı)

## Gerçek Çalıştırma (orkestratör tarafından doğrulandı)
```
python -m pytest tests/test_baileys_grp_pagination.py -q
9 failed, 7 passed in 1.45s
```

## AC -> Test Mapping
1. AC-1 (pagination section) -> `test_baileys_pagination_html_section_exists` -> RED (bekleniyor)
2. AC-2 (izole render fonksiyonu, buton stili) -> `test_baileys_pagination_function_exists`, `test_baileys_pagination_function_uses_baileys_current_page`, `test_baileys_pagination_uses_acc_button_class`, `test_baileys_pagination_uses_arrow_characters` -> RED (bekleniyor)
3. AC-3 (≤20 kayıtta gizleme) -> `test_baileys_pagination_visibility_logic` -> RED (bekleniyor)
4. AC-4 (ortak arama kutusu her iki *CurrentPage'i sıfırlar) -> `test_filterGroups_resets_both_current_pages` -> RED (bekleniyor)
5. AC-5 (loadBaileysGroups'un 3 dönüş noktasında pagination reset) -> `test_loadBaileysGroups_calls_renderBaileysGrpPagination_all_exit_points` -> RED (bekleniyor)
6. AC-6 (pagination hatası ana listeyi bozmamalı) -> Yapısal testle doğrulanamaz, `verify` adımında e2e/manuel kontrol edilecek.

## Regresyon Testleri (7/7 PASS)
- `test_items_per_page_not_redefined`, `test_grp_row_class_preserved`, `test_grp_pagination_functions_untouched`, `test_bl_pagination_functions_untouched`, `test_bl_item_class_preserved`, `test_baileys_available_groups_list_container_exists`, `test_grp_search_input_and_filter_preserved`.

## Coverage / Quality Notes
- Bu görev atdd.md'nin kendi Test Strategy'sine göre %90 e2e-manuel ağırlıklı; yazılan 16 test sadece yapısal (string/regex) — gerçek runtime davranışını doğrulamıyor, `verify` adımında canlı tarayıcı testi gerekiyor (önceki iki pagination görevinde olduğu gibi).
- `plan.md`'nin kritik bulgusu (filterGroups()'un Baileys bloğunun `baileysSearchMatches` deseniyle yeniden yazılması gerektiği) test dosyasına doğru yansıtılmış (`test_filterGroups_resets_both_current_pages`).
