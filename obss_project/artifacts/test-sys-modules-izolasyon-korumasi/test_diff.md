# Test Diff — test-sys-modules-izolasyon-korumasi

> Codex kotası dolu; bu task'ta test/implementasyon istisnai olarak Claude
> tarafından yazıldı, kullanıcı onaylıdır (bkz. `saga` skill Bölüm C).

## Yeni Dosya
`tests/test_conftest_sys_modules_pollution.py` — 11 test, 2 sınıf.

## AC → Test Eşlemesi
| AC | Test | Kırmızı doğrulandı mı |
|---|---|---|
| AC-1 (kirlilik yok → sessiz) | `test_no_pollution_returns_empty` | ✅ (implementasyon öncesi `ModuleNotFoundError: tests.conftest` ile fail) |
| AC-2 (bir modül kirli → tespit + isimlendirme) | `test_one_polluted_project_module_detected`, `test_plain_mock_instance_also_detected`, `test_hook_stops_pytest_when_module_level_pollution_persists` (gerçek subprocess) | ✅ |
| AC-3 (geçici monkeypatch → yanlış pozitif yok) | `test_hook_allows_clean_run_with_temporary_function_scoped_monkeypatch` (gerçek subprocess) | ✅ |
| AC-4 (çoklu kirlilik → hepsi listelenir) | `test_multiple_polluted_modules_all_listed` | ✅ |
| AC-5 (hiç import edilmemiş → hata değil) | `test_module_not_present_at_all_not_flagged` | ✅ |
| Kapsam Dışı (3.parti mock'lar meşru) | `test_third_party_mocks_never_flagged` | ✅ |
| Sınır kontrolü (yanlış prefix eşleşmesi) | `test_similarly_named_non_project_module_not_false_flagged` | ✅ |
| Plan.md liste tutarlılığı | `test_project_own_module_prefixes_matches_real_project_structure` | ✅ |

## Kırmızı Kanıt (implementasyon öncesi)
```
ModuleNotFoundError: No module named 'tests.conftest'
1 error in 0.69s
```

## Yeşil Kanıt (implementasyon sonrası)
```
11 passed in 3.19s
```

## Canlı Doğrulama — Hook Gerçekten Çalıştı
Yeni `conftest.py` tam suite'e (`pytest -q`) eklenince, hook **gerçek bir
önceden bilinmeyen kirliliği** yakaladı:
```
KIRLENME TESPIT EDILDI: src.utils.config, src.utils.reporter gercek modul
degil, bir MagicMock/Mock instance'i.
```
Kaynak: `test_webhook_server_threading.py`'nin (önceki görevde SADECE
`src.parsers.veri_cekici_ayristirici`'yi düzelttiğimiz dosya) aynı desende
iki DAHA ham `sys.modules` ataması vardı, onlar da geri alınmıyordu. Bu
görev kapsamında (aynı dosya, aynı düzeltme deseni) ikisi de `del` ile
düzeltildi. **Bu, hook'un iddia edilen amacını canlı olarak kanıtlıyor** —
manuel bulunması muhtemelen aylar sürerdi (ilk ikisi gibi), hook saniyeler
içinde buldu.

## Regresyon Kontrolü
Tam suite (`pytest -q`, CI'nin birebir komutu) → **301 passed, 0 failed**
(önceki 290'dan +11 yeni test).

## Test Piramidi
Unit (9/11, ~%82): `find_polluted_project_modules` saf fonksiyon testleri
Integration (2/11, ~%18): gerçek pytest alt-süreciyle (subprocess) hook'un
GERÇEKTEN pytest'i durdurduğunu/durdurmadığını doğrulayan 2 test
E2E (0/11): N/A — ATDD'de zaten uygulanamaz olarak işaretlenmişti

Not: ATDD hedefi (60/40/0) ile gerçekleşen (82/18/0) arasındaki fark —
saf fonksiyon mantığı beklenenden daha fazla dal içeriyordu (sınır
kontrolü, çoklu-modül, 3.parti hariç tutma), integration testleri (2
adet) yine de hook'un uçtan uca gerçek davranışını (subprocess ile)
kanıtlıyor.
