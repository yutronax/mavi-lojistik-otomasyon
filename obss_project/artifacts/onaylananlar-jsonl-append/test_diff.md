# Test Diff — onaylananlar-jsonl-append
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_onaylananlar_jsonl_append.py` (508 satır, pytest + `unittest.mock`,
senkron — Flask route'ları async değil).

## AC → Test eşleşmesi

| AC | Test | Durum (red step) |
|---|---|---|
| AC-1 (tekli onay, mevcut içerik hiç okunmaz) | `TestSingleApprovalNoRead::test_unprocessed_approve_appends_without_reading` | FAIL |
| AC-2 (toplu onay, tek append, okuma yok) | `TestBulkApprovalNoRead::test_approve_message_appends_all_without_reading` | FAIL |
| AC-3 (bellek profili, 30K+ satır büyük dosya) | `TestMemoryProfileLargeFile::test_large_jsonl_append_memory_bounded` | FAIL |
| AC-4 (dosya yoksa otomatik oluşur) | `TestFileCreationIfNotExists::test_file_created_on_first_append` | FAIL |
| AC-6 (kısmi başarı: geçersiz lokasyon atlanır) | `TestPartialSuccessInvalidLocations::test_approve_message_skips_invalid_locations` | FAIL |
| AC-7 (hiçbir şey yapılamadı: tüm sevkiyatlar geçersiz) | `TestNoActionWhenNothingToDo::test_approve_message_no_append_when_all_invalid` | PASS (mevcut validasyon davranışı zaten doğru) |
| AC-7 (hiçbir şey yapılamadı: mesaj bulunamadı) | `TestNoActionWhenNothingToDo::test_approve_message_message_not_found_no_append` | PASS (mevcut davranış zaten doğru) |
| Yardımcı (response format) | `TestResponseFormat::*` (2 test) | PASS (mevcut davranış zaten doğru) |

**Doğrulanmış sonuç:** `python -m pytest tests/test_onaylananlar_jsonl_append.py -v --tb=short` → **5 passed, 4 failed** — düzeltiyorum, gerçek sonuç: **4 passed, 5 failed** (bağımsız olarak çalıştırılıp teyit edildi).

## Test tekniği notları
- `json.load`'ın `AssertionError` fırlatacak şekilde patch'lenmesi ("okuma
  YASAK") kullanıldı — bu, AC-1/AC-2/AC-3'ün "mevcut içerik hiç okunmaz"
  gereksinimini yapısal olarak zorluyor (sadece dolaylı bir bellek ölçümüne
  güvenmiyor). Mevcut (eski) kod bu exception'ı kendi `try/except Exception:`
  bloğunda yuttuğu için görünen FAIL nedeni "dosya pretty-printed çok
  satırlı JSON dizisi olarak yazılmış, JSONL formatında değil" şeklinde
  ortaya çıkıyor — yapısal olarak doğru ve gerçek bir red step.
- AC-3 (bellek testi), gerçek 5MB+ bir JSONL dosyası (30.000 satır)
  üzerinde `psutil` ile RSS ölçüyor, MUTLAK değeri değil BASELINE'DAN
  FARKI (<100MB) assert ediyor — bu, önceki incident'ın (149MB dosya →
  969MB bellek) kök nedenini (tam dosya okuma) doğrudan hedefleyen, hem
  yapısal (json.load yasağı) hem ölçümsel (RSS farkı) çift güvenceli bir
  test.
- AC-5 (migration script) bu test dosyasının kapsamı DIŞINDA bırakıldı —
  ayrı bir script, code-copilot'ta ayrıca ele alınacak.

## Sıradaki adım
`code-copilot` — bu testleri (`tests/test_onaylananlar_jsonl_append.py`)
yeşile çevirecek implementasyonu (`APPROVED_PATH` → `.jsonl`, saf append,
`_atomic_write` kullanılmıyor) ve migration script'ini (`scripts/migrate_onaylananlar_to_jsonl.py`, ayrı, testsiz ama manuel doğrulanacak) yazacak.
