# Code Diff — ai-hourly-spend-cap-ayarlar-panelinde

## Değiştirilen Dosyalar
- `src/api/admin_panel.py` (implementasyon)
- `tests/test_admin_panel_settings_cleanup.py` (eskimiş "tam 10 anahtar" varsayımı, bu görevin kasıtlı 11. anahtarına göre güncellendi — bkz. "Düzeltmeler")

## AC → Kod Karşılığı
- **AC-1**: `EDITABLE_ENV_KEYS`'e `"AI_HOURLY_SPEND_CAP_TRY"` eklendi. Frontend `loadSet()` JS'i zaten dinamik (`API_KEYS = ['DEEPSEEK_API_KEY','GROQ_API_KEY','GEMINI_API_KEY']` sabit listesinde olmayan her anahtar otomatik "SİSTEM AYARLARI" grubuna düşüyor) — ayrı bir HTML/JS değişikliği GEREKMEDİ, AC-1'in "maskelenmeden, Sistem Ayarları grubunda" gereksinimi otomatik karşılandı.
- **AC-2**: Mevcut `settings_save` akışı (atomic write, opsiyonel PM2 restart) değişmeden çalışıyor.
- **AC-S1**: `settings_save`'e, `updates` boş kontrolünden hemen sonra, `.env` okumadan ÖNCE, SADECE `AI_HOURLY_SPEND_CAP_TRY` için `float()` + negatif kontrolü eklendi. Başarısızsa 400, TÜM istek reddedilir (kısmi yazma yok).
- **AC-5**: Diğer anahtarlar için validasyon eklenmedi (`if "AI_HOURLY_SPEND_CAP_TRY" in updates` bloğu dışına hiçbir şey taşmıyor) — grep ile doğrulandı.

## Düzeltmeler (ilk taslaktan sonra)
Kendi bağımsız test çalıştırmamda (alt-ajanın raporu sadece yeni test dosyasını tek başına çalıştırmıştı, kombine çalıştırmamıştı) bir REGRESYON buldum: `tests/test_admin_panel_settings_cleanup.py`'deki `test_editable_count_is_ten` ve `test_get_settings_excludes_start_end_hour` testleri "tam olarak 10 anahtar" varsayımını sabit kodlamıştı — bu, ÖNCEKİ görevin (web-admin-panel-ayarlar-temizlik-tasarim) doğru sonucuydu ama BU görev (AI_HOURLY_SPEND_CAP_TRY ekleme, AC-1) kasıtlı olarak 11. anahtarı ekliyor. Bu gerçek bir kod hatası değil, eskimiş bir test varsayımıydı — ikinci bir Haiku alt-ajan dispatch'iyle `expected_keys` set'ine yeni anahtar eklendi ve `test_editable_count_is_ten` → `test_editable_count_is_eleven` olarak güncellendi.

## Doğrulama
`python -m pytest tests/test_admin_panel_settings_cleanup.py tests/test_admin_panel_ai_spend_cap.py -v` → **25/25 PASS** (orkestratör tarafından bağımsız çalıştırıldı, iki dosya BİRLİKTE).

## CAVEMAN Self-Review
- Yeni dosya, yeni soyutlama, yeni yardımcı fonksiyon yok.
- Validasyon SADECE `AI_HOURLY_SPEND_CAP_TRY`'a özel bir `if` bloğu (7 satır) — genel bir validasyon şeması kurulmadı (bilinçli, atdd.md Risks'te not edildi).
- Frontend'e dokunulmadı (zaten dinamik render, ihtiyaç yoktu).
