# Plan — baileys-uretim-gecisi
_Reference: atdd.md_

## 🔑 Kritik mimari bulgu (atdd.md'nin Unknowns'unu çözüyor + yeni bir karar gerektiriyor)

Kod taraması şunu ortaya çıkardı:

1. **Süreç yöneticisi zaten PM2** — `ecosystem.config.js`'de iki app var:
   `mavi-lojistik-server` (`vps_main.py`) ve `mavi-admin-panel`
   (`admin_panel.py`). Sunucu Linux (`.venv/bin/python3` interpreter).
   → atdd.md Unknown #2 çözüldü.

2. **`WHAPI_AVAILABLE` zaten bir "opsiyonel Whapi" flag'i** ama sadece
   `ImportError`'a bağlı (env-var'la kontrol edilmiyor) — `fetch_new_messages_batch`
   içinde `if not WHAPI_AVAILABLE: return 0` var (satır 586).
   → atdd.md Unknown #1'in YARISI çözüldü: fetch'i kapatmanın hazır bir
   kancası var, ama bunu bir env-var'a bağlamak için küçük bir kod
   değişikliği gerekiyor (import'u bozmadan).

3. **`webhook_server.py`'nin `run_server()`'ı VPS üretiminde HİÇ ÇALIŞMIYOR**
   — sadece `src/gui/masaustu_uygulama.py` (masaüstü GUI) tetikliyor.
   `vps_main.py` sadece `orchestrator.run_loop()` çağırıyor, webhook
   sunucusunu hiç başlatmıyor. **Bu, bridge.js'in production'da mesajı
   nereye POST edeceği sorusunu açık bırakıyor** — `/baileys-webhook`
   endpoint'i şu an sadece GUI açıkken (kullanıcının kendi bilgisayarında)
   var oluyor, VPS'te değil.
4. **İki ayrı `OrchestratorSDK()` singleton'ı** — `vps_main.py`'nin kendi
   instance'ı ile `webhook_server.py`'nin modül-seviyesi `orchestrator`'ı
   FARKLI nesneler. İkisini aynı anda VPS'te ayrı process olarak
   çalıştırmak, aynı JSON dosyalarına (data/mesajlar.json vb.) iki ayrı
   process'in eşzamanlı yazması demek — ciddi veri bozulması riski.
5. **`vps_main.py`'nin kendine özgü bir davranışı var:** `is_working_hours()`
   (07:00-23:00 dışında uyku modu) — `webhook_server.py`'nin `run_server()`'ında
   bu YOK. Basitçe entrypoint değiştirmek bu özelliği kaybettirir.

### Karar (kullanıcıya onaylatılacak — bu, atdd.md'nin ötesinde yeni bir mimari seçim)
**`vps_main.py`'yi genişletmek**, `webhook_server.py`'nin `run_server()`'ını
üretimde ayrı bir process olarak çalıştırmamak. Somut olarak:
- `vps_main.py`, kendi `OrchestratorSDK()` instance'ını oluşturduktan sonra,
  `webhook_server.py`'deki `WhapiWebhookHandler`/`_handle_baileys_event`
  mantığını (kod kopyalamadan, import ederek) **aynı process içinde, ayrı
  bir thread'de** bir `HTTPServer` olarak başlatacak — `webhook_server.py`'nin
  kendi `orchestrator` singleton'ı yerine `vps_main.py`'nin instance'ını
  kullanacak şekilde parametrize edilecek.
- `is_working_hours()` mantığı korunur, sadece webhook sunucusu thread'i
  eklenir (mesai dışı saatlerde de dinlemeye devam edebilir ya da
  `is_working_hours()`'a bağlanabilir — **bu bir Open Question**, aşağıda).
- Bu sayede TEK bir `OrchestratorSDK()` instance'ı, hem periyodik döngüden
  (artık Whapi'siz, sadece "temizlik" işlevi görebilir) hem de Baileys
  webhook'undan gelen mesajları aynı kuyruğa/dosyalara yazar — çakışma riski
  ortadan kalkar.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `src/parsers/veri_cekici_ayristirici.py` | `run_loop()`'a yeni bir `WHAPI_POLLING_ENABLED` env-var kontrolü eklenecek (AC uyumlu, `WHAPI_AVAILABLE`'ı bozmadan — `get_channel_risk` gibi ikincil fonksiyonlar hâlâ import edilebilir kalsın, sadece `fetch_new_messages_batch`'in aktif çağrılması durdurulsun) | medium — üretim ana döngüsüne dokunuluyor |
| `vps_main.py` | Kendi `OrchestratorSDK()` instance'ıyla, `webhook_server.py`'den import edilen handler mantığını kullanan bir `HTTPServer` thread'i eklenecek (`/baileys-webhook` artık VPS'te de dinlenir, tek orchestrator instance'ı paylaşılır) | high — üretim entrypoint'i değişiyor, dikkatli test gerekir |
| `src/api/webhook_server.py` | `_handle_baileys_event`'in orchestrator'ı parametre olarak alabilmesi için küçük bir refactor (şu an modül-seviyesi `orchestrator` singleton'ına sabit) — `vps_main.py`'nin kendi instance'ını enjekte edebilmesi için | medium — mevcut GUI kullanımını (masaüstü) bozmayacak şekilde geriye dönük uyumlu olmalı |
| `ecosystem.config.js` | `mavi-lojistik-server` app'ine `sidecar/bridge.js`'i ayrı bir PM2 app olarak ekle (Node interpreter, `WEBHOOK_URL` env-var'ı VPS'in kendi localhost portuna işaret edecek) | low — ekleme, mevcut app'lere dokunmuyor |

## New Files
Yok — mevcut dosyalar genişletiliyor.

## Dependencies
- `sidecar/bridge.js` zaten `WEBHOOK_URL` ortam değişkenini okuyor (epic #43'te eklendi) — VPS'te `http://127.0.0.1:<port>/baileys-webhook`'a işaret edecek.
- `src/utils/config.py::WHATSAPP_POLL_INTERVAL` — periyodik döngünün ne sıklıkta çalıştığı, `WHAPI_POLLING_ENABLED=0` olsa bile döngünün kendisi (temizlik/health-check amaçlı) devam edip etmeyeceği netleştirilmeli.

## Migration Required?
Hayır — kod/config değişikliği, şema/veri değişikliği yok.

## Risks
atdd.md'deki riskler aynen geçerli, ek olarak:
- **Yeni risk (bu plan aşamasında bulundu):** `vps_main.py`'ye yeni bir HTTP server thread'i eklemek, mevcut `is_working_hours()` uyku mantığıyla nasıl etkileşeceği netleşmeden yapılırsa, mesai dışı saatlerde gelen mesajların sessizce kaybolması riski var (ya da tam tersi, uyku modunun hiç işe yaramaması).
- İki farklı `OrchestratorSDK()` instance'ının (vps_main.py + webhook_server.py) YANLIŞLIKLA aynı anda VPS'te ayrı process olarak çalıştırılması riski — bu plan bunu önlemek için "webhook_server.py'yi ayrı process olarak ASLA VPS'te başlatma" kuralını netleştiriyor, code-copilot bu kurala uymalı.

## Kararlar (kullanıcıya soruldu, netleşti)
1. **Mesai dışı davranış:** Webhook HTTP server thread'i `is_working_hours()` uyku modundan **bağımsız** — her zaman dinlemeye devam eder, gelen mesajlar kuyruğa eklenir. Sadece asıl İŞLEME (parser/Gemini çağrısı) mesai saatlerine bağlı kalabilir (mevcut `run_loop`/worker mantığı zaten bunu yapıyor gibi görünüyor — code-copilot doğrulayacak). Hiçbir mesaj kaybolmaz.
2. **Port:** `8080` (mevcut varsayılan, `webhook_server.py`'nin GUI'de kullandığı port ile aynı) — GUI ve VPS aynı anda çalışmayacağı için çakışma riski yok, tutarlılık korunuyor.

Açık soru kalmadı.
