# Test Diff — onaylananlar-cache-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_onaylananlar_cache_fix.py` (yeni, pytest + `unittest.mock`,
senkron — Flask route'ları async değil; `APPROVED_PATH` her testte
`tempfile` ile izole ediliyor, gerçek 143MB'lık production dosyasına
dokunulmuyor).

## AC → Test eşleşmesi

| AC | Test | Durum (red step) |
|---|---|---|
| AC-1 (tekli onay, tam dosya okunmaz) | `TestAC1SingleApproval::test_ac1_no_json_load_on_approval` | FAIL |
| AC-2 (toplu onay, tek cache güncelleme + tek disk yazımı) | `TestAC2BulkApproval::test_ac2_no_json_load_bulk` | FAIL |
| AC-2 (count doğru dönüyor, cache'den bağımsız) | `TestAC2BulkApproval::test_ac2_count_returned_correctly` | PASS (mevcut davranış zaten doğru) |
| AC-3 (cache bir kez yüklenir, ikinci onayda tekrar okunmaz) | `TestAC3LazyLoadOnce::test_ac3_second_approval_no_reread` | FAIL |
| AC-4 (dosya yoksa atomik oluşturulur) | `TestAC4MissingFile::test_ac4_missing_file_creates_atomically` | PASS (mevcut `_atomic_write` zaten bu davranışı sağlıyor, cache implementasyonu bunu bozmamalı — regresyon testi) |
| AC-5 (kısmi başarı: geçersiz lokasyon atlanır) | `TestAC5PartialBulk::test_ac5_skip_invalid_location` | PASS (mevcut davranış zaten doğru) |
| AC-6 (hiçbir şey yapılamadı, sevkiyat yok) | `TestAC6NoShipments::test_ac6_empty_shipments_no_write` | PASS (mevcut davranış zaten doğru) |
| AC-6 (hiçbir şey yapılamadı, geçersiz lokasyon) | `TestAC6NoShipments::test_ac6_invalid_location_single_no_write` | PASS (mevcut davranış zaten doğru) |

**Doğrulanmış sonuç:** `python -m pytest tests/test_onaylananlar_cache_fix.py -v --tb=short`
→ **5 passed, 3 failed** (bağımsız olarak çalıştırılıp teyit edildi).

## Düzeltme geçmişi (bu görevde, test-copilot dispatch'i sırasında)
İlk yazımda test dosyası `sys.modules['flask'] = MagicMock()` ile TÜM
`flask` modülünü stub'lıyordu (bu venv'de Flask kurulu olmadığı için
sub-agent'ın kendi çözümüydü). Bu, `@app.route`/`@require_auth` ile süslenen
`unprocessed_approve` fonksiyonunun modül seviyesinde GERÇEK KOD OLMAKTAN
ÇIKIP alakasız bir MagicMock nesnesine dönüşmesine yol açtı — bu da 3 testin
(`test_ac1`, `test_ac4`, `test_ac6_invalid_location_single_no_write`) ya
sahte-yeşil (hiçbir gerçek kod çalışmadığı için assertion'lar anlamsızca
geçiyordu) ya da yanlış nedenle kırmızı olmasına neden oldu. Bağımsız
doğrulamayla yakalandı. Düzeltme: (1) Flask gerçekten bu venv'e kuruldu
(`pip install flask`), (2) mock satırı kaldırıldı, (3) `unprocessed_approve`
çağrıları `.__wrapped__(...)` ile (require_auth'u bypass ederek) çağrıldı,
(4) `jsonify()`'ın gerektirdiği Flask app context için
`admin_panel.app.test_request_context()` bloğu eklendi. Sonuç bağımsız
olarak doğrulandı: tam olarak 3 test (AC-1, AC-2, AC-3) gerçek
`AssertionError` ile FAIL, 5 test gerçek nedenle PASS.

## Sıradaki adım
`code-copilot` — bu testleri (`tests/test_onaylananlar_cache_fix.py`)
yeşile çevirecek implementasyonu `plan.md`'nin "Files to Modify" listesine
göre yazacak (`_approved_cache`, `_approved_lock`, `_load_approved()`,
`_save_approved()` — `_unprocessed_cache` deseni birebir taklit edilerek,
AMA arka plan mtime-polling thread'i OLMADAN).
