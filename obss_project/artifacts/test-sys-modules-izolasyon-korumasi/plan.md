# Plan — test-sys-modules-izolasyon-korumasi
_Reference: atdd.md_

## Files to Modify
Yok — repo'da `conftest.py` hiç yok (ne kökte ne `tests/` altında,
`Glob` ile doğrulandı).

## New Files
| File | Purpose |
|------|---------|
| tests/conftest.py | `pytest_collection_finish(session)` hook'u — collection bitince `sys.modules`'taki proje-kendi modüllerinin (bkz. aşağıda liste) gerçek mi mock mu olduğunu kontrol eder, kirlilik varsa `pytest.exit()` ile net bir mesajla süreci durdurur. |

## Proje-Kendi Modül Tanımı (ATDD'nin Risks bölümündeki açık soru — burada netleştiriliyor)
Kök dizindeki gerçek `.py` dosyaları taranarak (`ls *.py`) belirlendi:
- `text_gen_parser` (kök dizin, AI ayrıştırma orkestrasyonu — en riskli,
  bugünkü olayda tam da bunun bir "kardeş" modülü kirlenmişti)
- `vps_main` (kök dizin, prod giriş noktası)
- `production_parser` (kök dizin)
- `src` prefix'i ile başlayan HER ŞEY (`src.parsers.veri_cekici_ayristirici`,
  `src.api.webhook_server`, `src.api.admin_panel`, `src.utils.*` vb.)

`rthook_backports` kapsam DIŞI bırakıldı — bu bir PyInstaller runtime hook'u,
iş mantığı içermiyor, test tarafından mock'lanması anlamsız/olası değil.

Bu liste `tests/conftest.py`'de bir sabit (`PROJECT_OWN_MODULE_PREFIXES`)
olarak tanımlanacak — ATDD'nin Risks bölümünde işaretlendiği gibi,
gelecekte yeni bir kök-dizin modülü eklenirse bu listenin MANUEL
güncellenmesi gerekecek (`pm2-process-izleme-ve-uyari` görevindeki
`EXPECTED_PM2_PROCESSES` ile aynı bilinen bakım deseni).

## Dependencies
- `unittest.mock.MagicMock`/`Mock` — kirlilik tespiti `isinstance(module, (MagicMock, Mock))` ile yapılacak (hem `MagicMock` hem düz `Mock` kullanan test dosyaları var, ikisi de yakalanmalı).
- `sys.modules` — doğrudan Python'ın kendi modül cache'i, ek bağımlılık yok.
- Hiçbir mevcut test dosyasına DOKUNULMUYOR (ATDD'nin Kapsam Dışı kararı).

## Migration Required?
Hayır — yeni bir test-altyapı dosyası, şema/veri migration kavramı yok.

## Risks
(atdd.md'den taşınan + planlama sırasında netleşen)
- `PROJECT_OWN_MODULE_PREFIXES` listesi yukarıda netleştirildi (4 kök-dizin
  modülü + `src.` prefix'i) — ama gelecekte yeni bir kök modül eklenirse
  MANUEL güncellenmesi gerekecek, bilinen/kabul edilmiş bir sınırlama.
- `pytest_collection_finish` hook'u YANLIŞ modül adı eşleştirirse (ör.
  `src` prefix kontrolü çok geniş/dar olursa) false-positive/negative
  riski — test stratejisindeki unit testler (sahte `sys.modules`
  senaryolarıyla) bunu doğrulayacak.
- Hook `pytest.exit()` çağırdığında CI'da "test failure" değil "session
  interrupted" gibi görünebilir — bu ATDD'nin AC-2'sinin gerektirdiği
  "açık ve net" davranış, ama CI raporlama arayüzünde farklı görünebileceği
  not düşülüyor (kabul edilebilir, amaç zaten "sessizce geçmemesi").

## Open Questions
Yok — ATDD'nin tek açık sorusu (proje-kendi modül tanımı) yukarıda
gerçek kod taranarak netleştirildi, Sonnet 5 alt-ajanına dispatch
gerekmiyor.
