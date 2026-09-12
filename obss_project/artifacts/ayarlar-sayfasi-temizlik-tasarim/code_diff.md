# Code Diff — ayarlar-sayfasi-temizlik-tasarim

## Değiştirilen Dosya
- `src/gui/pages/settings_page.py`

## AC → Kod Karşılığı
- **AC-1**: `whapi_token_field`, `whapi_url_field`, `refresh_interval_field` tanımları, `load_settings`'teki karşılıkları ve `get_view`'daki "WhatsApp API Yapılandırması"/"Uygulama Tercihleri" bölümleri kaldırıldı.
- **AC-2**: `save_settings`'teki config dict artık sadece `llm_url`/`llm_model`/`llm_keys` içeriyor; `os.environ["LLM_BASE_URL"/"LLM_MODEL"/"GROQ_API_KEYS"]` seti korunuyor.
- **AC-3**: `load_settings` eski config'te whapi/refresh_interval anahtarları olsa da bunları okumuyor (hata fırlatmıyor, zararsız).
- **AC-4**: Validasyon eklenmedi — boş string olduğu gibi kaydediliyor (mevcut davranış).
- **AC-5**: `save_settings`'teki `try/except` + `_show_error` korunuyor.
- **AC-6 (Tasarım Yönü)**: LLM bölüm başlığına ikon eklendi (`ft.Icons.SMART_TOY`), kart gölgesi güçlendirildi (`blur_radius=25, spread_radius=2`), `border_radius` 15→20, `TextField`'lar `filled=True, bgcolor=SURFACE_LIGHT, focused_border_color=ACCENT` ile modernize edildi.

## Düzeltmeler (ilk taslaktan sonra)
1. İlk taslakta `ft.Icons.BRAIN` kullanılmıştı — bu geçersiz bir Flet Icons üyesi (doğrulandı: `hasattr(ft.Icons, 'BRAIN')` → False), çalışma zamanında `AttributeError` fırlatırdı. `ft.Icons.SMART_TOY` ile değiştirildi (doğrulandı: mevcut).
2. Kullanılmayan `AppStyles` import'u kaldırıldı (satır 4 sadeleştirildi).
3. `tests/test_settings_page_cleanup.py`'de iki fixture sorunu bulunup düzeltildi (implementasyon değil, test dosyası):
   - `pytest-asyncio` kurulu olmadığı için `@pytest.mark.asyncio` + `async def` deseni projenin gerçek konvansiyonuna (`asyncio.run(...)` içinde senkron test) çevrildi.
   - `flet` modülü tek bir `MagicMock()` ile stub'landığı için `ft.TextField(...)`'in her çağrısı aynı nesneyi döndürüyordu (üç alan aynı `.value`'yu paylaşıyordu) — `TextField.side_effect` ile her çağrıda bağımsız mock dönmesi sağlandı.

## Doğrulama
`python -m pytest tests/test_settings_page_cleanup.py -v` → **18 passed** (bağımsız olarak orkestratör tarafından çalıştırılıp doğrulandı, alt-ajan özetine güvenilmedi).

## CAVEMAN Self-Review
- Yeni dosya yok, yeni soyutlama/yardımcı fonksiyon yok.
- Kaldırılan alanlar dışında davranış değişmedi (LLM kaydetme/env-set/hata yakalama akışı aynı).
