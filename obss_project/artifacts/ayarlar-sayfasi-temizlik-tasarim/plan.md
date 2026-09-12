# Plan — ayarlar-sayfasi-temizlik-tasarim
_Reference: atdd.md_

Frontend-pipeline: tetikleyici mekanik olarak eşleşti (atdd.md "Görsel/UI kriteri" dolu), ANCAK bu görev bir web/browser UI değil — Flet tabanlı **native masaüstü GUI** (Python widget ağacı, DOM/HTML yok). `frontend-pipeline`'ın Discover/Audit adımları Playwright MCP'ye (gerçek tarayıcı) dayanıyor ve bu pencereyi süremez; `frontend-design`/`better-*` skilleri de web bileşen varsayımıyla çalışır. Bu yüzden `frontend-pipeline` bilinçli olarak atlandı (sessizce değil — bu not o kararın kaydı). Görsel doğrulama yine de atlanmıyor: `verify` adımında ekran görüntüsü + `vision-test` skill'i (screenshot tabanlı, browser'a bağımlı değil) ile yapılacak.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/gui/pages/settings_page.py | AC-1: whapi_token_field/whapi_url_field/refresh_interval_field tanımları (satır 38-57), load_settings'teki karşılıkları (67-69), save_settings'teki config sözlüğü anahtarları (82-84) ve get_view'daki "WhatsApp API Yapılandırması"/"Uygulama Tercihleri" bölümleri (138-147) kaldırılacak. AC-6/Tasarım Yönü: kalan "Yapay Zeka (LLM) Yapılandırması" kartı ikon+etiket başlık, zenginleştirilmiş gölge/köşe, modern TextField görünümü ile yeniden düzenlenecek. | low |

## New Files
Yok.

## Dependencies
- `src.gui.styles.AppColors` / `AppStyles` — renk/gölge kaynağı, DEĞİŞTİRİLMEYECEK (sadece referans alınacak, AC-6 diğer sayfaların temel temasını bozmamalı).
- `src.services.data_service_async.AsyncDataService` / `DataService` — `load_config("app_settings")` / `save_config("app_settings", config)` sözleşmesi korunacak; sadece config sözlüğünden whapi/refresh_interval anahtarları çıkarılacak (AC-3: eski dosyada bu anahtarlar kalsa da zararsız, okunmuyorlar zaten).
- `src.utils.api_key_manager.APIKeyManager` — `load_keys(reason='settings_update')` çağrısı korunacak, LLM akışıyla ilgili, dokunulmayacak.
- `os.environ["LLM_BASE_URL"/"LLM_MODEL"/"GROQ_API_KEYS"]` set edilmesi (satır 89-91) korunacak — AC-2.

## Migration Required?
Hayır. Config JSON şeması/formatı değişmiyor (kapsam dışı, atdd.md'de belirtildi); sadece UI'nin artık yazmadığı anahtarlar var, eski dosyalarda kalıntı olarak durabilirler (AC-3).

## Risks
- Tasarım zenginleştirmesi (AC-6) sırasında `management_center.py`/`server_control.py` ile temel renk/tema tutarlılığının kazara bozulması riski — bu dosyalar bu görevde değiştirilmiyor, sadece görsel referans olarak kullanılacak.
- `refresh_interval_field`'ın `int(...)` dönüşümü save_settings'te (satır 84) kaldırılınca config sözlüğünden o anahtarın tamamen çıkması gerekiyor — kısmi kaldırma (field silinip config'de anahtar kalması) tutarsızlık yaratır, ikisi birlikte kaldırılmalı.

## Open Questions
Yok — atdd.md'nin "Tasarım Yönü" bölümü ve mevcut kod okuması, code-copilot için yeterli somutlukta. Sonnet 5 alt-ajanına dispatch gerekmedi.
