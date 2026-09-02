# Test Diff — dedup-active-ids-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_dedup_active_ids_fix.py` (7 test, senkron pytest,
`OrchestratorSDK.__new__()` ile ağır bağımlılıklar atlanarak hafif bir
instance kuruluyor).

## AC → Test eşleşmesi

| AC | Test | Durum (red step) |
|---|---|---|
| AC-1 (sadece ilçe → save + mark) | `TestAC1_OnlyIlceShipmentSaved::test_ilce_only_shipment_saved_and_handled` | FAIL |
| AC-2 (sıra: mark önce, active_ids temizliği sonra) | `TestAC2_ActiveIdsRemovedAfterMark::test_task_wrapper_active_ids_removed_after_save_results` | PASS (mevcut `save_results` içi sıra zaten doğru) |
| AC-3 (exception'da da mark) | `TestAC3_ExceptionHandling::test_task_wrapper_calls_mark_on_exception` | FAIL |
| AC-4 (active_ids regresyonu) | `TestAC4_RegressionActiveIdsDuplicate::test_message_not_enqueued_if_in_active_ids` | PASS (mevcut davranış zaten doğru) |
| AC-5 (body-hash regresyonu) | `TestAC5_RegressionBodyHashDuplicate::test_message_not_enqueued_if_body_hash_in_active` | PASS (mevcut davranış zaten doğru) |
| Yardımcı (entegrasyon) | `TestIntegrationFlowSaveResultsFlow::*` (2 test) | PASS (mevcut davranış zaten doğru) |

**Doğrulanmış sonuç:** `python -m pytest tests/test_dedup_active_ids_fix.py -v` → **5 passed, 2 failed** (bağımsız olarak çalıştırılıp teyit edildi).

## Düzeltme geçmişi (test-copilot dispatch'i sırasında)
İlk yazımda 2 ciddi sahte-yeşil sorunu bulundu, bağımsız doğrulamayla yakalandı:
1. **AC-3'ün kritik assertion'ı yorum satırına alınmıştı** (`# orch.data_service.mark_id_handled.assert_called_with(msg_id)`) — implementasyon olsa da olmasa da test sessizce PASS ediyordu, hiçbir ayırt edici gücü yoktu. Yorum satırından çıkarılıp aktif hale getirildi.
2. **AC-2'nin testi yanlış fonksiyonu (`save_results` doğrudan) çağırıyordu**, `_task_wrapper`'ın `finally` bloğunu hiç tetiklemiyordu — bu yüzden asıl iddia ettiği "sıra" garantisini test etmiyordu (ayrıca kullanılmayan ölü bir yardımcı fonksiyon vardı). Test, `_task_wrapper`'ı tam akışıyla çağıracak ve `mark_id_handled` çağrıldığı ANDAKİ `active_ids` durumunu (hâlâ içeride olmalı) + işlem TAMAMLANDIKTAN SONRAKİ durumu (çıkarılmış olmalı) doğrulayacak şekilde yeniden yazıldı.

## Sıradaki adım
`code-copilot` — bu testleri (`tests/test_dedup_active_ids_fix.py`) yeşile
çevirecek implementasyonu yazacak: `save_results`'taki `has_valid_shipment`
kontrolüne ilçe alanlarını da ekleme, `_task_wrapper`'ın `except` bloğuna
`mark_id_handled` çağrısı ekleme.
