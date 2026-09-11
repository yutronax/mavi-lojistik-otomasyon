# Code Diff — test-sys-modules-izolasyon-korumasi

> Codex kotası dolu; bu task'ta test/implementasyon istisnai olarak Claude
> tarafından yazıldı, kullanıcı onaylıdır (bkz. `saga` skill Bölüm C).

## Yeni Dosya
`tests/conftest.py` — repo'da daha önce hiç yoktu.

### Yeni Semboller
- `_discover_project_own_module_prefixes()` — **red-team düzeltmesi**: ilk versiyonda statik/hardcoded bir tuple'dı (`("text_gen_parser", "vps_main", "production_parser", "src")`), bağımsız inceleme bunun `rthook_backports.py`'yi kaçırdığını buldu (ironik: hook'un önlemeye çalıştığı TAM "insana güvenme" hatası, kendi bakım listesinde oluşmuştu). Artık kök dizindeki TÜM `.py` dosyalarını `glob` ile dinamik tarıyor + `src` paket kökünü ekliyor — manuel liste bakımı gerekmiyor.
- `PROJECT_OWN_MODULE_PREFIXES` — `_discover_project_own_module_prefixes()`'in sonucu (modül import zamanında bir kez hesaplanır).
- `_is_project_own_module(name)` — tam sınır kontrolü (`name == prefix` veya `name.startswith(prefix + ".")`), `srclib` gibi yanlış eşleşmeleri önlüyor.
- `find_polluted_project_modules(modules)` — saf fonksiyon, `sys.modules`'a bağımlı değil (test edilebilirlik için parametre olarak alıyor).
- `pytest_collection_finish(session)` — pytest hook'u, collection bitince kirlilik varsa `pytest.exit()` ile süreci durdurur.

## Değiştirilen Dosya (bu görevin bir YAN ÜRÜNÜ — bkz. aşağıda)
`tests/test_webhook_server_threading.py` — yeni hook'un CANLI OLARAK
yakaladığı, önceki görevde (deepseek-balance-diff sonrası CI fix'inde)
gözden kaçan İKİ EK `sys.modules` ataması (`src.utils.reporter`,
`src.utils.config`) da aynı `del sys.modules[...]` deseniyle düzeltildi.
Bu, ATDD'nin "mevcut 4 dosyaya dokunulmayacak" kararına AYKIRI DEĞİL —
o karar `test_junk_message_filter.py`, `test_hourly_spend_cap.py`,
`test_whapi_removed.py`, `test_dedup_active_ids_fix.py` için geçerliydi
(zararsız 3.parti mock'ları). `test_webhook_server_threading.py` zaten
BAŞKA bir görevde elle düzeltilmiş bir dosyaydı — bu görev SADECE aynı
dosyadaki, aynı hata sınıfının GÖZDEN KAÇAN iki örneğini, hook'un kendisi
tarafından tespit edilince düzeltti (yeni bir kapsam değil, aynı dosyanın
eksik kalan düzeltmesinin tamamlanması).

## Kasıtlı Olarak Değiştirilmeyenler
- `test_junk_message_filter.py`, `test_hourly_spend_cap.py`,
  `test_whapi_removed.py`, `test_dedup_active_ids_fix.py` — ATDD'nin
  Kapsam Dışı kararı gereği dokunulmadı (zararsız 3.parti mock'ları,
  refactor bu görevin işi değil).

## CAVEMAN / Definition of Done Kontrolü
- Karar mantığı (`find_polluted_project_modules`) ile pytest entegrasyonu
  (`pytest_collection_finish`) ayrı fonksiyonlarda — test edilebilirlik.
- Yeni bağımlılık eklenmedi (`unittest.mock`, `pytest` zaten mevcut).
- Magic number/string yok — `PROJECT_OWN_MODULE_PREFIXES` tek bir yerde
  tanımlı sabit, plan.md'de gerekçeli.
- Derin nesting yok.
