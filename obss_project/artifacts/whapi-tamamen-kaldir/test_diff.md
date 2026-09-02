# Test Diff — whapi-tamamen-kaldir
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_whapi_removed.py` — 14 test, `test_dedup_active_ids_fix.py`'nin aynı `sys.modules` stub deseniyle (`google.genai`/`dotenv`/`pymongo` mock'lanarak) import zincirindeki gerçek ortam sorunu çözüldü (ilk taslak `ImportError: cannot import name 'genai'` ile collection'da çöküyordu, düzeltildi).

Gerçek çalıştırmayla doğrulandı: **10 passed, 4 failed** (RED — beklenen, route'lar henüz silinmedi).

## AC → Test Eşlemesi
| AC | Davranış | Test Fonksiyonu | Durum |
|---|---|---|---|
| AC-1 | `/api/groups/available` silinmeli → 404 | `TestDeletedRoutesReturn404::test_groups_available_route_deleted_returns_404` | RED (beklenen) |
| AC-2 | `/api/whatsapp-health` silinmeli → 404 | `TestDeletedRoutesReturn404::test_whatsapp_health_route_deleted_returns_404` | RED (beklenen) |
| AC-1/2 ek | Auth olmadan da 404 | `test_deleted_routes_without_auth_also_404` | RED (beklenen) |
| AC-3 (düzeltilmiş) | `handle_webhook_event()`, `WHAPI_POLLING_ENABLED=0` iken `fetch_all_messages` çağırmamalı | `TestWebhookEventFetchGate::test_webhook_event_respects_whapi_polling_disabled` | GREEN (zaten, ama gate henüz eklenmedi — dikkat, bkz. not) |
| AC-3/6 | Kod tabanında aktif Whapi ağ çağrısı (WATSAPP_TOKEN okuma dahil) kalmamalı | `TestNoWhapiNetworkCalls::test_no_direct_whapi_urls_in_vps_files` | RED (beklenen, `admin_panel.py:798`'de `WHATSAPP_TOKEN` okuyan satır tespit edildi — route silinince otomatik gidecek) |
| Regresyon | `/api/groups` (kayıtlı) değişmemeli | `TestRegressionSavedGroups::test_groups_get_route_unchanged` | GREEN |
| Regresyon | `whapi_fetcher.py` hâlâ import edilebilir (GUI için) | `TestRegressionWhapiImport::test_whapi_fetcher_module_importable` | GREEN |

## Dikkat — code-copilot İçin Not
`test_webhook_event_respects_whapi_polling_disabled` testi şu an GREEN görünüyor ama bu, plan.md'nin işaret ettiği gerçek gate'in HENÜZ eklenmediği bir durumda "yanlışlıkla" geçiyor olabilir (örn. mock'lama OrchestratorSDK'yı tam instantiate edemediği için fonksiyon hiç çalışmamış olabilir — false positive). code-copilot implementasyonu yaptıktan sonra bu testin GERÇEKTEN anlamlı çalıştığını (gate olmadan RED, gate ile GREEN) `verify` adımında ayrıca doğrulanmalı.

## code-copilot İçin Bağlayıcı Bulgular
- `admin_panel.py:798` civarında `WHATSAPP_TOKEN` okuyan satır `/api/whatsapp-health` route'unun içinde — bu route silinince otomatik olarak temizlenmiş olacak.
- `test_no_direct_whapi_urls_in_vps_files` testi `gate.whapi.cloud` ve `WHATSAPP_TOKEN` string'lerini (yorum satırları hariç, `import` içeren satırlar hariç) VPS-ilgili dosyalarda arıyor — bu testin GREEN olması, iki route'un silinmesi ve `handle_webhook_event`'e gate eklenmesiyle otomatik sağlanacak.
