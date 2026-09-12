# Code Diff — web-admin-panel-ayarlar-temizlik-tasarim

## Değiştirilen Dosya
- `src/api/admin_panel.py`

## Diff Özeti (orkestratör tarafından `git diff` ile doğrulandı)
```diff
 EDITABLE_ENV_KEYS = [
     ...
-    "START_HOUR",
-    "END_HOUR",
     "AUTO_SUBMIT",
     ...
 ]
 ...
+#set-fields input:focus{border-color:var(--acc);outline:none}
 </style>
 ...
-'<p ...>SİSTEM AYARLARI</p>'
+'<p ...;padding-bottom:8px;border-bottom:1px solid var(--border)">SİSTEM AYARLARI</p>'
-'<p ...>AI API ANAHTARLARI</p>'
+'<p ...;padding-bottom:8px;border-bottom:1px solid var(--border)">AI API ANAHTARLARI</p>'
```

## AC → Kod Karşılığı
- **AC-1/AC-S1**: `EDITABLE_ENV_KEYS`'ten `START_HOUR`/`END_HOUR` silindi — hem GET görünürlüğünü hem POST yazılabilirliğini aynı anda kapatıyor (tek liste, tek nokta).
- **AC-2**: Dokunulmadı — `loadSet()` zaten `d.editable`'a bağlı dinamik render, liste küçülünce otomatik uyum sağladı.
- **AC-3/AC-4**: Dokunulmadı — `settings_get`/`settings_save` route mantığı değişmedi, mevcut davranış (atomic write, eski satırlara dokunmama) korundu.
- **AC-5 (Tasarım Yönü)**: Grup başlıklarına `border-bottom:1px solid var(--border)` + `padding-bottom:8px` eklendi (ayraç); `#set-fields input:focus{border-color:var(--acc);outline:none}` scoped kuralı eklendi (global `input:focus` DEĞİL — diğer sekmeler etkilenmedi). API anahtarı maskeleme/göz ikonu davranışı dokunulmadan kaldı.

## Doğrulama
- `python -m pytest tests/test_admin_panel_settings_cleanup.py -v` → **12/12 PASS** (orkestratör tarafından bağımsız çalıştırıldı).
- `git diff HEAD -- src/api/admin_panel.py` okunarak diff'in gerçekten minimal ve kapsamda kaldığı doğrulandı (global CSS seçicisi yok, yeni dosya/soyutlama yok).
- Görsel doğrulama: `INDEX_HTML` proje dışı bir scratchpad dizininde statik olarak çıkarılıp yerel bir HTTP sunucusunda (backend'e/gerçek verilere dokunmadan) açıldı, Ayarlar sekmesi sahte veriyle render edildi — ekran görüntüsüyle (1) `START_HOUR`/`END_HOUR` artık görünmüyor, (2) grup başlığı altında ayraç çizgisi var, (3) input'a tıklanınca turuncu (`--acc`) focus kenarlığı çıkıyor, doğrulandı.

## CAVEMAN Self-Review
- Yeni dosya, yeni soyutlama, yeni yardımcı fonksiyon yok.
- Diff 3 küçük, birbirinden bağımsız değişiklik: (1) liste küçültme, (2) 1 satır scoped CSS, (3) 2 satırlık inline stil eklemesi.
- Global stil/davranış değişikliği yok — diğer sekmeler (mesajlar, kara liste, loglar) etkilenmedi.
