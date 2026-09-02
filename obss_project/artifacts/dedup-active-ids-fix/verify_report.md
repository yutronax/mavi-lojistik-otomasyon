# Verify Report — dedup-active-ids-fix
_Reference: atdd.md, code_diff.md, test_diff.md_

## Verification Gates
| # | Gate | Result | Evidence / Reason |
|---|------|--------|--------------------|
| 1 | Dosya konumu | PASS | `git status --short` ile `M src/parsers/veri_cekici_ayristirici.py`, `?? tests/test_dedup_active_ids_fix.py` teyit edildi. |
| 2 | Build/derleme | PASS | `ast.parse` ile sözdizimi doğrulandı. |
| 3 | Supabase şema/canlı doğrulama | N/A | Proje Supabase kullanmıyor. |
| 4 | Lint | N/A | CI sadece `pytest -q` çalıştırıyor. |
| 5 | Type check | N/A | Repo'da type-checker konfigürasyonu yok. |
| 6 | Unit testler | PASS | `pytest -q` → **48 passed**, bağımsız olarak tekrarlandı. |
| 7 | E2E testler | N/A | Bu görevde e2e altyapısı yok. |
| 8 | Lighthouse (performans) | N/A | Web UI değişikliği yok. |
| 9 | Erişilebilirlik | N/A | Aynı sebep. |
| 10 | Güvenlik taraması | PASS (yanlış pozitifler açıklandı) | `secrets` gate'i satır 168'de "Secret Keyword" bulgusu verdi — `Read` ile doğrulandı: bu sadece `api_key = "test_key"` (test verisi, gerçek kimlik bilgisi değil), test dosyasında. `python_sast` 3 B108 bulgusu (mock edilmiş `/tmp/test.json` yolları, test dosyasında, gerçek dosya yazımı yok) verdi. İkisi de `tests/test_dedup_active_ids_fix.py`'de, üretim kodunda (`veri_cekici_ayristirici.py`) SIFIR bulgu. `python_deps` PASS. |
| 11 | AI code review | PASS (`approve`, 2 medium kabul edildi/ertelendi, 1 low) | `obss-red-team`: kritik/bloklayıcı bulgu yok. 2 medium (mark_id_handled'ın kendisinin başarısız olduğu nadir "double-fault" senaryosu; geçici/kalıcı hata ayrımı yapılmaması) atdd.md'nin zaten kabul ettiği tavizler kapsamında, ayrı takip görevi olarak bırakıldı — asıl kök neden (deterministik il/ilçe uyuşmazlığı) tam kapatıldı. Detay: red_team.json. |
| 12 | Görsel regresyon | N/A | Web UI kapsamda değil. |
| 13 | İnsan onayı | PENDING | Kullanıcı onayı bekleniyor. |

## AC → Test Mapping
1. [Critical] Sadece ilçe → kalıcı işaretlenir → `TestAC1_OnlyIlceShipmentSaved::test_ilce_only_shipment_saved_and_handled` → PASS
2. [Critical] Sıra: mark önce, active_ids sonra → `TestAC2_ActiveIdsRemovedAfterMark::test_task_wrapper_active_ids_removed_after_save_results` → PASS
3. [High] Exception'da da işaretle → `TestAC3_ExceptionHandling::test_task_wrapper_calls_mark_on_exception` → PASS
4. [High] active_ids regresyonu → `TestAC4_RegressionActiveIdsDuplicate::test_message_not_enqueued_if_in_active_ids` → PASS
5. [Medium] body-hash regresyonu → `TestAC5_RegressionBodyHashDuplicate::test_message_not_enqueued_if_body_hash_in_active` → PASS
6. [Medium] Canlı log gözlemi → Kod testi kapsamı dışı, deploy sonrası manuel gözlemle doğrulanacak.

## Coverage / Quality Notes
- atdd.md'nin 5 kod-test edilebilir AC'sinin tümü kapsanmış (AC-6 doğası gereği canlı gözlem gerektiriyor).
- Test-copilot adımında 2 sahte-yeşil test bulunup düzeltildi: AC-3'ün kritik assertion'ı yorum satırına alınmıştı (sessizce PASS ediyordu), AC-2'nin testi yanlış fonksiyonu çağırıp asıl iddia ettiği sırayı hiç test etmiyordu. İkisi de düzeltilip bağımsız doğrulandı.
- Değişiklik minimal ve odaklı: 2 dosya konumunda, toplam ~5 satır (1 satır genişletme + 4 satır exception-handling ekleme).
