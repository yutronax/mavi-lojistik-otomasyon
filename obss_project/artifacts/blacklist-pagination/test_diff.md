# Test Diff — blacklist-pagination
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
- `tests/test_blacklist_pagination.py` (yeni, 14 test, Haiku alt-ajanı tarafından yazıldı, `tests/test_gruplar_tab_ui.py`'nin structural-string-test deseniyle)

## Gerçek Çalıştırma (orkestratör tarafından doğrulandı)
```
python -m pytest tests/test_blacklist_pagination.py -q
9 failed, 5 passed in 1.85s
```

## AC -> Test Mapping
1. AC-1 (pagination section + happy path) -> `test_bl_pagination_html_section_exists` -> RED (bekleniyor)
2. AC-2 (izole render fonksiyonu, buton stili) -> `test_bl_pagination_function_exists`, `test_bl_pagination_function_uses_bl_current_page`, `test_bl_pagination_uses_acc_button_class`, `test_bl_pagination_uses_arrow_characters` -> RED (bekleniyor)
3. AC-3 (≤20 kayıtta gizleme) -> `test_bl_pagination_visibility_logic` -> RED (bekleniyor)
4. AC-4 (arama sonrası sayfa 1'e reset) -> `test_loadBl_calls_renderBlPagination` -> RED (bekleniyor)
5. AC-5 (silme sonrası sayfa clamp) -> Ayrı bir yapısal test yazılmadı — plan.md'nin çözdüğü gibi bu davranış `loadBl()`'ün her zaman `renderBlPagination(1)` çağırmasından otomatik geliyor, `test_loadBl_calls_renderBlPagination` bunu dolaylı kapsıyor. Gerçek runtime doğrulaması (silme sonrası DOM'un gerçekten değiştiği) `verify` adımında e2e/manuel yapılacak.
6. AC-6 (pagination hatası ana listeyi bozmamalı) -> Yapısal string testiyle doğrulanamaz (try/catch varlığı test edilebilir ama davranışsal izolasyon runtime gerektirir) — `verify` adımında e2e ile kontrol edilecek, burada test edilmedi.

## Regresyon Testleri (5/5 PASS)
- `test_items_per_page_not_redefined` — `ITEMS_PER_PAGE` paylaşılan sabit, tekrar tanımlanmamış.
- `test_bl_item_class_preserved` — `.bl-item` CSS class'ı hâlâ mevcut.
- `test_grp_pagination_functions_preserved` — Gruplar'ın `renderGrpPagination`/`currentPage`/`grpSearchMatches`'ine dokunulmamış.
- `test_bl_list_container_exists` — `#bl-list` hâlâ mevcut.
- `test_bl_q_search_input_exists` — `#bl-q` arama input'u hâlâ mevcut.

## Coverage / Quality Notes
- Bu görev atdd.md'nin kendi Test Strategy'sine göre %90 e2e-manuel ağırlıklı; yazılan 14 test sadece **yapısal** (string/regex) — gerçek runtime davranışını (sayfa geçişi, silme sonrası clamp, hata izolasyonu) doğrulamıyor. Bu proje deseninin (`test_gruplar_tab_ui.py`) bilinçli bir sınırlaması — `verify` adımında bu boşluk manuel/e2e ile kapatılmalı, sessizce "test edildi" sayılmamalı.
- `test_blCurrentPage_not_named_currentPage` ve `test_bl_pagination_and_grp_pagination_separate_functions` testleri, code-copilot'un izolasyon gereksinimini (AC-2, Risks) doğru uyguladığını doğrulayacak — bunlar da şu an RED.
