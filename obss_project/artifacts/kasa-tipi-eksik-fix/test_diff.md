# Test Diff — kasa-tipi-eksik-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_kasa_tipi_eksik_fix.py` (yeni, pytest + `unittest.mock`, gerçek dosya G/Ç ve API çağrısı yok; `VehicleTypeMatcher` testleri gerçek `data/yuk_tipi.json` ile çalışıyor — bu saf/yerel dosya okuma, dış bağımlılık değil)

## AC → Test eşleşmesi

| AC | Test | Durum (red step) |
|---|---|---|
| AC-1 (happy path, regresyon yok) | `TestHappyPathRuleMatch::test_rule_match_happy_path_no_uncertainty_flag` | PASS (mevcut davranış zaten doğru) |
| AC-2 (ipucu yok → flag+sebep) | `TestNoHintUncertainty::test_no_hint_sets_uncertainty_ipucu_yok` | FAIL |
| AC-3 (ipucu var, kural eşleşmedi → flag+sebep+log) | `TestHintButNoRuleMatch::test_hint_but_no_match_writes_unmatched_log` | FAIL |
| AC-4 (çok rotalı bağımsız değerlendirme) | `TestMultiRouteIndependentEvaluation::test_multi_route_independent_flags` | FAIL |
| Yardımcı (VehicleTypeMatcher temel davranış) | `TestVehicleTypeMatcherKeywordExtraction::*` (3 test) | PASS (mevcut davranış) |
| Edge case (eksik alan, boş rota listesi) | `TestEdgeCases::*` (2 test) | PASS (mevcut davranış) |

**Doğrulanmış sonuç:** `python -m pytest tests/test_kasa_tipi_eksik_fix.py -v` → **6 passed, 3 failed** (bağımsız olarak çalıştırılıp teyit edildi).

## Not
İlk yazımda 2 test (AC-3'ün dosya-yazma kontrolü, AC-4'ün rota-bağımsızlığı kontrolü) gerçek assertion içermiyordu — AC-3'teki dosya yazma kontrolü `if mock_save.called:` ile KOŞULLUYDU (implementasyon hiç yazmasa da geçerdi), AC-4 sadece "kasa_tipi alanı var mı" diye bakıyordu (flag farkını hiç doğrulamıyordu). İkinci bir Haiku dispatch'i ile düzeltildi: AC-3'te `assert mock_save.called` koşulsuz zorunlu yapıldı, AC-4'te Route 2'nin (`ANKARA->BURSA`, hiç ipucu yok) kesinlikle `kasa_tipi_belirsiz=True, sebep="ipucu_yok"` olması gerektiği doğrudan assert edildi. Düzeltme sonrası bağımsız olarak doğrulandı: 6 passed, 3 failed.

## Sıradaki adım
`code-copilot` — bu testleri (`tests/test_kasa_tipi_eksik_fix.py`) yeşile çevirecek implementasyonu `plan.md`'nin "Files to Modify" listesine ve "Kararlar" bölümüne göre yazacak (Seçenek A: yuk_tipi.json'dan türetilen anahtar kelime seti; log yazma sorumluluğu text_gen_parser.py'de; panel UI değişikliği YOK).
