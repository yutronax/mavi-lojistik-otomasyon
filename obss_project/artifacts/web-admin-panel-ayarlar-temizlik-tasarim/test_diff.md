# Test Diff — web-admin-panel-ayarlar-temizlik-tasarim

## Oluşturulan Dosya
- `tests/test_admin_panel_settings_cleanup.py` (yeni, 12 test fonksiyonu, 5 sınıf)

## AC → Test Eşlemesi
| AC | Test sınıfı/fonksiyonları |
|---|---|
| AC-1 (GET START_HOUR/END_HOUR yok) | `TestSettingsGetCleanup` — 2 test |
| AC-3 (POST geçerli ayar kaydı) | `TestSettingsSave` — 2 test |
| AC-4 (eski .env satırlarına dokunulmaz) | `TestOldEnvLinesPreserved` — 2 test |
| AC-S1 (threat-model, allowlist dışı anahtar reddi) | `TestAllowlistEnforcement` — 2 test |
| Regresyon (boş updates, auth) | `TestRegressions` — 4 test |

## İlk Çalıştırma Durumu (red step) — orkestratör tarafından bağımsız doğrulandı
`python -m pytest tests/test_admin_panel_settings_cleanup.py -v` → **4 failed, 8 passed**.
Fail edenler beklenen: `test_get_settings_excludes_start_end_hour`, `test_editable_count_is_ten` (START_HOUR/END_HOUR hâlâ `EDITABLE_ENV_KEYS`'te), `test_disallowed_key_not_written_to_env`, `test_only_disallowed_keys_returns_400` (allowlist henüz küçültülmedi). Pass edenler zaten mevcut davranışla uyumlu regresyon testleri (auth, boş updates, temel kaydetme).

## Not
Test dosyası gerçek `.env`'e dokunmuyor — `ENV_PATH`'i `monkeypatch`/`patch.object` ile `tmp_path` altında geçici bir dosyaya yönlendiriyor (`temp_env_file` fixture'ı).
