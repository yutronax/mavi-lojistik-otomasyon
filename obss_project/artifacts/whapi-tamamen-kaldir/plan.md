# Plan — whapi-tamamen-kaldir
_Reference: atdd.md (AC-3 ve AC-7 kod keşfi sonucu düzeltildi, dosyanın kendisine işlendi)_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | `/api/groups/available` route'u (satır 864-, `gate.whapi.cloud/groups` çağıran) ve `/api/whatsapp-health` route'u (`gate.whapi.cloud/health` çağıran) silinir. `INDEX_HTML` sabitindeki "kayıtsız grup tarama" bölümü (buton + `loadAvailableGroups()`/`grpAdd()` JS fonksiyonları + `checkWaHealth()` çağrısı) kaldırılır. AC-1, AC-2. | medium (frontend layout etkilenir, `verify` adımında canlı kontrol gerekir) |
| src/parsers/veri_cekici_ayristirici.py | `check_blocking_risk()` (satır 289-, `get_channel_risk()`/`calculate_channel_risk()` çağıran) — VPS akışında (`run_loop`'un `WHAPI_POLLING_ENABLED=0` erken-çıkışı, satır 1099) zaten ASLA tetiklenmiyor, bu KORUNUYOR bilgi amaçlı doğrulandı, kod DEĞİŞMEYECEK (regresyon testiyle kanıtlanacak). **Gerçek değişiklik**: `handle_webhook_event()` (satır 364-, "webhook odaklı fetch_all_messages", satır 421-437) içine `WHAPI_POLLING_ENABLED` kontrolü eklenir — Whapi'nin eski bir webhook kaydı hâlâ VPS'e push yaparsa (kod dışı, Whapi tarafındaki bir ayar) bu fonksiyon şu an KOŞULSUZ `fetch_all_messages()` çağırıyor, bu son bir savunma hattı olarak kapatılmalı. AC-3 (düzeltilmiş hali). | medium (canlı mesaj akışını etkilememeli, dikkatli test gerekir) |

## New Files
Yok.

## Dokunulmayacak Dosyalar (bilinçli, kapsam dışı — kod keşfinde netleşti)
- `src/fetchers/whapi_fetcher.py` — GUI (`masaustu_uygulama.py`, `management_center.py`, `yonetim_merkezi.py`, `managers.py`) tarafından aktif kullanılıyor, dosya SİLİNMEZ. atdd.md AC-3 buna göre düzeltildi.
- `src/api/webhook_server.py`'nin `WhapiWebhookHandler` class'ı, `run_server()`, `setup_webhook()` — GUI (`masaustu_uygulama.py` satır 87, 3806) tarafından import ediliyor, PAYLAŞILAN dosya. VPS zaten sadece `make_webhook_handler_class`'ı kullanıyor (satır 156-), `/baileys-webhook` path'i `else` dalından (Whapi'nin `handle_webhook_event` yolu) KASITLI OLARAK AYRI tutulmuş (satır 116-128, mevcut kod yorumu bunu doğruluyor). Bu dosyaya DOKUNULMAYACAK — sadece `veri_cekici_ayristirici.py`'deki `handle_webhook_event`'in İÇİNE gate eklenecek (yukarıdaki tablo).
- `vps_main.py` — sadece yorum satırlarında Whapi geçiyor, aktif çağrı YOK (doğrulandı, `grep` ile teyit edildi). Dokunulmayacak.
- `.env`'deki `WHATSAPP_TOKEN` — kullanıcı onayıyla kapsam dışı, VPS canlı `.env`'ine dokunulmayacak.
- `/api/groups` route'u (kayıtlı gruplar, `data/chat_groups.json` okuyor) — Whapi'ye hiç bağımlı değil, DEĞİŞMEYECEK.

## Dependencies
- `veri_cekici_ayristirici.py`'nin modül-seviyesi `from src.fetchers.whapi_fetcher import ... ; WHAPI_AVAILABLE = True/False` (satır 76-81, try/except) KORUNUYOR — bu import GUI ile paylaşılan dosyanın normal çalışması için gerekli, sadece VPS'in bu import'u ÇALIŞTIRMA ZAMANINDA kullanmadığı doğrulanıyor.
- `admin_panel.py`'deki `_pm2()`, `require_auth`, mevcut Flask route deseni — silme işlemi sadece iki route'u ve karşılık gelen frontend bloklarını kaldırıyor, başka bir desene bağımlılık yok.

## Migration Required?
No — sadece kod satırları/route'lar siliniyor, şema/veri değişikliği yok.

## Risks
(atdd.md'den taşındı, kod keşfiyle netleşti/genişledi)
- **[Yeni bulgu]** Whapi'nin (eski, muhtemelen artık geçersiz) bir webhook kaydı hâlâ VPS'in `/`(veya `/baileys-webhook` dışındaki herhangi bir) path'ine POST yapıyorsa, `handle_webhook_event()` şu an koşulsuz Whapi'ye canlı bir API çağrısı (`fetch_all_messages`) yapıyor — bu, "VPS'ten Whapi'ye hiçbir bağlantı kalmasın" hedefini ihlal eden gizli bir kod yolu. Plan'daki `WHAPI_POLLING_ENABLED` gate'i eklenerek kapatılıyor.
- Frontend değişikliği (`admin_panel.py`'nin `INDEX_HTML` sabiti) — önceki görevlerde (panel-baileys-qr-gosterimi) bu dosyada statik incelemenin kaçırdığı bir JS-string-kaçış hatası canlı testte bulunmuştu. `verify` adımında AYNI titizlikle canlı tarayıcı testi ZORUNLU.
- Regresyon riski: `check_blocking_risk()`'in gerçekten hiç tetiklenmediğini doğrulayan bir test yoksa, gelecekte `run_loop`'un erken-çıkış mantığı (satır 1099) yanlışlıkla değiştirilirse bu sessizce yeniden Whapi'ye bağlanabilir — `test-copilot` bunu regresyon testi olarak eklemeli (AC-3'ün "asla çağrılmaz" iddiasını doğrulayan bir unit test, `run_loop`'u gerçekten çalıştırmadan, mock ile `WHAPI_POLLING_ENABLED=0` iken `fetch_new_messages_batch`'in çağrılıp çağrılmadığını kontrol eden).

## Open Questions
Yok — kod keşfi sırasında çıkan iki büyük belirsizlik (whapi_fetcher.py'nin GUI bağımlılığı, webhook_server.py'nin paylaşımı) kullanıcıya doğrudan soruldu ve netleşti (atdd.md'ye işlendi). Yeni bulunan `handle_webhook_event` savunma-hattı riski, atdd.md'nin AC-3'ünün ("VPS process'i Whapi'ye ağ isteği atmaz") doğal bir uzantısı — kapsam genişletmiyor, sadece daha eksiksiz kapatıyor, ek onay gerektirmiyor.
