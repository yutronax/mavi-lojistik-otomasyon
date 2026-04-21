# 📋 FLET UYGULAMASI — TÜM BİLEŞENLER ANALİZİ

> **Giriş Dosyası:** `src/gui/flet_app.py`
> **Toplam Dosya Sayısı:** 9 modül
> **Framework:** Flet 0.82.2 (Python tabanlı Flutter)
> **Son Analiz Tarihi:** 2026-04-21

Bu belge, Flet tabanlı arayüzün (`flet_app.py` + sayfa/bileşen modülleri) **tüm sınıflarını**, **metotlarını**, **UI bileşenlerini** ve **veri akışlarını** kapsamlı olarak belgelemektedir.

---

## 📐 MİMARİ GENEL BAKIŞ

```
┌─────────────────────────────────────────────────────────────────────┐
│                     flet_app.py (188 satır)                        │
│                     Ana Giriş + Sidebar + Router                    │
├─────────┬──────────────┬──────────────┬──────────────┬─────────────┤
│ SIDEBAR │  Operasyon   │  Yönetim     │  Sunucu      │   Loglar    │
│ Navig.  │  Merkezi     │  Paneli      │  Kontrolü    │   Sayfası   │
│         │ (1043 satır) │ (842 satır)  │ (221 satır)  │ (183 satır) │
├─────────┴──────────────┴──────────────┴──────────────┴─────────────┤
│                  Ayarlar Sayfası (153 satır)                        │
├────────────────────────────────────────────────────────────────────┤
│  BILEŞENLER: styles.py │ log_viewer.py │ managers.py │ tag_sel.   │
│              (66 satır) │ (183 satır)   │ (517 satır) │ (140 satır)│
└────────────────────────────────────────────────────────────────────┘
```

### Modül Haritası

| Dosya | Satır | Sınıf(lar) | Açıklama |
|-------|-------|------------|----------|
| `flet_app.py` | 188 | — (fonksiyonel) | Ana giriş, sidebar, sayfa yönlendirici |
| `pages/operation_center.py` | 1043 | `OperationCenterPage` | Mesaj görüntüleme, sevkiyat yönetimi, servis kontrolü |
| `pages/management_center.py` | 842 | `ManagementCenterPage` | Yük tanımlama, mahalle, grup, kara liste yönetimi |
| `pages/server_control.py` | 221 | `ServerControlPage` | Uzak sunucu izleme ve kontrol |
| `pages/settings_page.py` | 153 | `SettingsPage` | API anahtarları ve uygulama ayarları |
| `components/log_viewer.py` | 183 | `LogViewer`, `LogPage` | Canlı log izleme (dosya takibi) |
| `components/managers.py` | 517 | `BlacklistManager`, `GroupManager` | Tkinter tabanlı eski yöneticiler (legacy) |
| `components/tag_selector.py` | 140 | `TagSelector` | Tkinter tabanlı etiket seçici (legacy) |
| `components/autocomplete.py` | 73 | `AutocompleteEntry` | Tkinter tabanlı otomatik tamamlama (legacy) |
| `styles.py` | 66 | `AppColors`, `AppGradients`, `AppStyles` | Tema, renkler, gölgeler |

### Veri Katmanları

| Katman | Dosya/Servis | Açıklama |
|--------|-------------|----------|
| `DataService` | `src/services/data_service.py` | Senkron JSON CRUD |
| `AsyncDataService` | `src/services/data_service_async.py` | Asenkron sarmalayıcı |
| `SubmissionQueue` | `src/services/submission_queue.py` | Arka plan gönderim kuyruğu |
| `YukBuradaSubmitter` | `tools/submit_approved_loads.py` | YükBurada API |
| `AsyncServerManager` | `src/utils/server_manager_async.py` | Uzak sunucu yönetimi |
| `APIKeyManager` | `src/utils/api_key_manager.py` | .env API anahtarları |

---

## 🔵 BÖLÜM 1: ANA UYGULAMA — `flet_app.py`

### 1.1 Fonksiyonlar

| # | Fonksiyon | Satır | Açıklama | Tetikleyici |
|---|-----------|-------|----------|-------------|
| 1 | `main(page)` | 18-184 | Ana giriş noktası: Tema uygular, sayfa nesnelerini oluşturur, sidebar + header + layout kurar, varsayılan "Yönetim" sayfasını yükler | `ft.run(main)` |
| 2 | `change_page(page_name)` | 55-95 | **Async sayfa yönlendirici:** ProgressRing gösterir → ilgili sayfanın `get_view()` metodunu çağırır → `main_content`'e yerleştirir. Hata durumunda error UI ve SnackBar gösterir | Sidebar tıklama |
| 3 | `create_nav_item(text, icon, page_name)` | 99-113 | Sidebar navigasyon öğesi oluşturur: ikon + metin + tıklama/hover efektleri, `_nav_refs` dict'ine kaydeder | Sidebar kurulumu |
| 4 | `_update_active_nav(page_name)` | 40-53 | Aktif sidebar öğesini vurgular (bgcolor, border, icon/text rengi), diğerlerini sıfırlar | `change_page` sonrası |
| 5 | `self_hover(e)` | 115-127 | Sidebar öğeleri hover efekti: aktif sayfa hariç hover renk değişimi uygular | Mouse hover |

### 1.2 UI Bileşenleri

| Bileşen | Satır | Tip | Açıklama |
|---------|-------|-----|----------|
| `sidebar` | 129-154 | `ft.Container` | Sol navigasyon paneli (250px genişlik), logo + 5 nav item + versiyon |
| `header` | 157-168 | `ft.Container` | Üst başlık çubuğu: "Hoş Geldiniz" + bildirim ikonu + avatar |
| `main_content` | 35-38 | `ft.Container` | Ana içerik alanı (expand=True), sayfa değişiminde içerik güncellenir |
| `layout` | 170-180 | `ft.Row` | Sidebar + (Header + Content) ana düzeni |

### 1.3 Sayfa Yönlendirme Haritası

| Sidebar Öğesi | İkon | Hedef Sayfa | Sınıf |
|---------------|------|-------------|-------|
| Operasyon Merkezi | `DASHBOARD_ROUNDED` | `op_center.get_view()` | `OperationCenterPage` |
| Yönetim Paneli | `ADMIN_PANEL_SETTINGS_ROUNDED` | `mgmt_center.get_view()` | `ManagementCenterPage` |
| Sunucu Kontrolü | `DNS_OUTLINED` | `srv_control.get_view()` | `ServerControlPage` |
| Sistem Logları | `TERMINAL_ROUNDED` | `log_page.get_view()` | `LogPage` |
| Ayarlar | `SETTINGS_ROUNDED` | `mgmt_center.get_view()` + Tab 4 seçimi | `ManagementCenterPage` → Tab 5 |

---

## 🟢 BÖLÜM 2: OPERASYON MERKEZİ — `OperationCenterPage`

> **Dosya:** `src/gui/pages/operation_center.py` (1043 satır)
> **Sınıf:** `OperationCenterPage`

### 2.1 Başlatma ve Durum Yönetimi

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 1 | `__init__(page)` | 26-284 | Sayfa referansı, DataService, UI state (cache, indexler, servis süreç), filtre dropdown, sol/orta/sağ panel UI bileşenlerini oluşturur | Uygulama başlangıcı |
| 2 | `_init_queue_async()` | 317-334 | `YukBuradaSubmitter` ve `SubmissionQueue`'yu executor'da lazy başlatır (tek seferlik) | İlk `load_data()` |
| 3 | `_safe_update(ctrl)` | 308-312 | Güvenli kontrol güncelleme (hata yutma) | Tüm UI güncellemeleri |

### 2.2 Veri Yükleme

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 4 | `load_data()` | 339-404 | **Ana veri yükleme (async):** Kuyruk başlat → zaman filtresi uygula → mesajları çek → sol/orta panel güncelle → sayaçları güncelle. Yükleme kilidi ile çoklu çağrı engeli | Yenile butonu / Filtre değişimi |
| 5 | `_refresh_messages_list()` | 409-486 | Sol panel mesaj listesini yeniler: zaman damgası, önizleme, sevkiyat badge'i, seçili vurgulama | `load_data` / `_select_message` |

### 2.3 Mesaj Navigasyonu

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 6 | `_select_message(mid)` | 491-498 | Mesaj seçer: `selected_mid` günceller → orijinal metin + sevkiyatları gösterir → highlight günceller | Mesaj kartı tıklama |
| 7 | `navigate_message(direction)` | 500-510 | Önceki/Sonraki mesaj navigasyonu (modüler wrap-around) | ◀ / ▶ butonları |
| 8 | `_update_nav_text()` | 512-516 | "3/15" formatında sayaç günceller | Navigasyon sonrası |

### 2.4 Orijinal Mesaj Görüntüleme

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 9 | `_update_message_display()` | 521-558 | Sol panel alt: mesaj metnini ve meta bilgileri (grup, gönderen, zaman) gösterir | Mesaj seçimi |

### 2.5 Sevkiyat Listesi

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 10 | `_update_shipments_for_message(mid)` | 563-751 | **Orta panel:** Seçili mesajın sevkiyatlarını kart formatında listeler — Güzergah, araç/kasa/yük tag'leri, fiyat, telefon, açıklama. Her kartta Onayla/Düzenle/Sil butonları | Mesaj seçimi |
| 11 | `_show_empty_center()` | 753-775 | Mesaj seçilmediğinde boş durum gösterir | Veri yokken |
| 12 | `_create_mini_stat(label, value_ctrl, icon)` | 289-306 | İstatistik mini kartı oluşturur (ikon + etiket + değer) | Sağ panel kurulumu |

### 2.6 Sevkiyat Düzenleme

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 13 | `open_edit_dialog(mid, idx)` | 780-973 | **Tam formlu düzenleme dialogu:** Firma adı, Nereden/Nereye (İl/İlçe), Araç/Kasa/Yük dropdown, Telefon, Fiyat, Açıklama. Yer değiştir butonu, Kaydet/İptal aksiyonları | ✏️ Düzenle butonu |
| 14 | `save_edit (closure)` | 858-892 | Dialog içinde: form verilerini sevkiyata yazar → dosyaya kaydeder → dialogu kapatır → listeyi günceller | 💾 KAYDET (dialog) |
| 15 | `_swap_locations (closure)` | 894-904 | Nereden ↔ Nereye il/ilçe değerlerini takaslar | ⇅ Yer Değiştir butonu |

### 2.7 Sevkiyat Aksiyonları

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 16 | `confirm_shipment(mid, idx)` | 978-993 | **Onaylama:** Onay tarihi ekle → kuyruğa ekle → onaylananlar kaydet → sevkiyatı listeden sil → tüm sevkiyat bittiyse mesajı sil → veriyi yenile | ✅ Onayla butonu |
| 17 | `delete_shipment(mid, idx)` | 995-1005 | **Silme:** Sevkiyatı listeden sil → mesaj boşsa mesajı sil → veriyi yenile | 🗑️ Sil butonu |

### 2.8 Servis Yönetimi

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 18 | `start_service()` | 1010-1022 | `veri_cekici_ayristirici.py`'yi subprocess olarak başlatır, durum ikonunu günceller | SERVİSİ BAŞLAT butonu |
| 19 | `stop_service()` | 1024-1031 | Subprocess'i terminate eder, durumu "Durdu" olarak günceller | SERVİSİ DURDUR butonu |
| 20 | `get_view()` | 1036-1042 | Arka planda `load_data()` başlatır, 3 panelli layout döndürür | Sayfa yönlendirme |

### 2.9 Yardımcı Fonksiyonlar (Modül Düzeyinde)

| # | Fonksiyon | Satır | Açıklama |
|---|-----------|-------|----------|
| 21 | `_safe_list(v)` | 11-17 | Değeri güvenli listeye çevirir (str/list/None) |
| 22 | `_first(lst)` | 20-22 | Listenin ilk elemanını döndürür (safe) |

### 2.10 UI Panel Yapısı

| Panel | Genişlik | İçerik |
|-------|----------|--------|
| **Sol Panel** (`left_pane`) | 300px | Mesaj listesi (ListView), navigasyon okları, orijinal mesaj metni, meta bilgiler |
| **Orta Panel** (`center_pane`) | expand | Sevkiyat kartları (ListView), zaman filtresi, yenile butonu |
| **Sağ Panel** (`right_pane`) | 240px | İstatistikler (mesaj/bekleyen sayaçları), servis durumu, başlat/durdur butonları |

---

## 🟡 BÖLÜM 3: YÖNETİM MERKEZİ — `ManagementCenterPage`

> **Dosya:** `src/gui/pages/management_center.py` (842 satır)
> **Sınıf:** `ManagementCenterPage`

### 3.1 Sekmeler (TabBar)

| Sekme # | Başlık | İkon | Setup Metodu |
|---------|--------|------|-------------|
| 0 | Yük Tanımlama | `INVENTORY_2_ROUNDED` | `_setup_yuk_tanim()` |
| 1 | Mahalle Yönetimi | `LOCATION_ON_ROUNDED` | `_setup_mahalle_sync()` |
| 2 | Grup Ayarları | `GROUPS_ROUNDED` | `_setup_gruplar()` |
| 3 | Kara Liste | `BLOCK_ROUNDED` | `_setup_kara_liste()` |
| 4 | Sistem Ayarları | `SETTINGS_ROUNDED` | `SettingsPage.get_view()` |

### 3.2 Yük Tanımlama Aksiyonları

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 1 | `_load_yuk_data()` | 41-63 | Dropdown seçeneklerini (araç/kasa/yük tipleri) ve mevcut yük tanımlarını yükler | Sekme açılışı / Yenile |
| 2 | `_refresh_yuk_list(filter_text)` | 72-106 | Yük tanımlarını listeler (ilk 100 adet limitli), filtre uygular | Arama / Yükleme sonrası |
| 3 | `_filter_yuk(e)` | 108-109 | Arama kutusu değişiminde listeyi filtreler | TextField on_change |
| 4 | `_save_yuk_tanimi(e)` | 111-142 | **Yeni yük tanımı kaydet:** Anahtar kelime + varyasyonlar üretir → kural oluşturur → JSON'a yazar → listeyi günceller | TANIMI KAYDET butonu |
| 5 | `_delete_yuk_tanimi(index)` | 144-154 | Tanımı siler, JSON'u günceller | 🗑️ Sil ikonu |

### 3.3 Mahalle Yönetimi Aksiyonları

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 6 | `_setup_mahalle_sync()` | 243-297 | Mahalle yönetim UI'ını kurar: İl/İlçe dropdown, mahalle listesi, yeni mahalle ekleme alanı | Tab kurulumu |
| 7 | `_load_il_data()` | 411-417 | `il_ilceler.json` verilerini yükler, İl dropdown'ını doldurur | Başlangıç |
| 8 | `_on_il_change(e)` | 419-425 | İl seçildiğinde ilçe dropdown'ını günceller, mahalle listesini temizler | İl dropdown seçimi |
| 9 | `_on_ilce_change(e)` | 427-428 | İlçe seçildiğinde mahalle listesini yeniler | İlçe dropdown seçimi |
| 10 | `_refresh_mahalle_list()` | 430-462 | Seçili il/ilçeye ait mahalleleri listeler (lokasyon ikonu + silme butonu) | İlçe değişimi |
| 11 | `_add_mahalle()` | 464-483 | Yeni mahalle ekler → JSON günceller → listeyi yeniler | ➕ Mahalle Ekle butonu |
| 12 | `_delete_mahalle(mname)` | 485-498 | Mahalleyi siler → JSON günceller → listeyi yeniler | 🗑️ Sil butonu |

### 3.4 Grup Yönetimi Aksiyonları

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 13 | `_setup_gruplar()` | 500-601 | İki panelli UI: Sol = Kayıtlı Gruplar, Sağ = WhatsApp'tan Çek | Tab kurulumu |
| 14 | `_load_groups_data()` | 698-727 | Kayıtlı grupları yükler ve listeler (ad + ID + silme butonu) | Başlangıç / Yenileme |
| 15 | `_add_group()` | 729-741 | Manuel grup ekler (ad + ID) → kaydeder → listeyi günceller | ➕ Grup Ekle butonu |
| 16 | `_delete_group(group_obj)` | 743-750 | Grubu siler → kaydeder → listeyi günceller | 🗑️ Sil butonu |
| 17 | `_fetch_whatsapp_groups()` | 752-783 | **WhatsApp API'den grup çekme:** Yükleniyor durumu → `fetch_groups()` çağır → listeyi doldur → durum güncelle | Grupları Çek butonu |
| 18 | `_fetch_whatsapp_groups_refresh_list(groups, saved_ids)` | 785-841 | Çekilen grupları listeler: kayıtlı/kayıtsız durumu, tek tıkla kaydet | `_fetch_whatsapp_groups` sonrası |

### 3.5 Kara Liste Aksiyonları

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 19 | `_setup_kara_liste()` | 603-645 | Kara liste UI: Numara girişi + engellenen numara listesi | Tab kurulumu |
| 20 | `_load_blacklist_data()` | 648-674 | Engellenen numaraları yükler ve listeler (blok ikonu + silme) | Başlangıç |
| 21 | `_add_blacklist()` | 676-686 | Numarayı kara listeye ekler → kaydeder → listeyi günceller | ➕ Ekle butonu |
| 22 | `_delete_blacklist(phone)` | 688-695 | Numarayı çıkarır → kaydeder → listeyi günceller | 🗑️ Sil butonu |

### 3.6 Genel Metodlar

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 23 | `get_view()` | 166-241 | Sayfa görünümü: TabBar + TabBarView oluşturur, önbellekler, arka planda veri yükler | Sayfa yönlendirme |
| 24 | `_safe_update(control)` | 65-70 | Güvenli kontrol güncelleme | Tüm UI güncellemeleri |
| 25 | `_show_error(msg)` | 156-159 | Hata SnackBar gösterir (kırmızı) | Hata durumları |
| 26 | `_show_success(msg)` | 161-164 | Başarı SnackBar gösterir (yeşil) | Başarılı işlemler |

---

## 🟣 BÖLÜM 4: SUNUCU KONTROLÜ — `ServerControlPage`

> **Dosya:** `src/gui/pages/server_control.py` (221 satır)
> **Sınıf:** `ServerControlPage`

### 4.1 Metod Haritası

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 1 | `__init__(page)` | 17-52 | `AsyncServerManager` oluşturur, status chip, CPU/RAM/Uptime text, terminal log alanı kurar | Uygulama başlangıcı |
| 2 | `_update_status()` | 55-86 | **Periyodik durum güncelleme (5 sn):** Sunucudan status çeker → chip/metric güncellemeleri | Arka plan task |
| 3 | `_refresh_logs(e)` | 88-93 | Sunucudan son 50 satır logu çeker → terminal kutusuna yazar | 🔄 Yenile butonu |
| 4 | `_run_command(cmd_type)` | 96-119 | **Sunucu komutu gönder:** restart / stop / start / pull (git). SnackBar ile sonuç gösterir, logları yeniler | Kontrol butonları |
| 5 | `_create_stat_card(title, icon, value_ref)` | 121-132 | Metrik kartı oluşturur (başlık + ikon + değer) | UI kurulumu |
| 6 | `get_view()` | 134-220 | Tam sayfa görünümü: Başlık + Metrikler + Kontrol Butonları + Terminal Kutusu. Arka plan task başlatır (tek seferlik) | Sayfa yönlendirme |

### 4.2 Kontrol Butonları

| Buton | Komut | Renk | Aksiyon |
|-------|-------|------|---------|
| Yeniden Başlat | `restart` | PRIMARY (mavi) | `manager.restart()` |
| Durdur | `stop` | DANGER (kırmızı) | `manager.stop()` |
| Başlat | `start` | SUCCESS (yeşil) | `manager.start()` |
| Kod Güncelle | `pull` | WARNING (amber) | `manager.git_pull()` |

### 4.3 İzleme Metrikleri

| Metrik | Bileşen | Güncelleme |
|--------|---------|-----------|
| CPU | `cpu_text` | Her 5 saniye |
| RAM | `mem_text` | Her 5 saniye |
| Uptime | `uptime_text` | Her 5 saniye |
| Durum | `status_chip` | Her 5 saniye (ÇALIŞIYOR / OFFLINE) |

---

## 🔴 BÖLÜM 5: AYARLAR SAYFASI — `SettingsPage`

> **Dosya:** `src/gui/pages/settings_page.py` (153 satır)
> **Sınıf:** `SettingsPage`

### 5.1 Metod Haritası

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 1 | `__init__(page)` | 10-44 | DataService, APIKeyManager oluşturur, form alanlarını kurar (Gemini Key, Whapi Token, URL, Refresh Interval) | Uygulama başlangıcı |
| 2 | `load_settings()` | 46-58 | `.env` dosyasından API anahtarlarını okur → form alanlarına yazar | Başlangıç / Yenile butonu |
| 3 | `save_settings(e)` | 60-76 | Form değerlerini `.env` + `config.json`'a yazar. SnackBar ile sonuç gösterir | AYARLARI KAYDET butonu |
| 4 | `get_view()` | 88-152 | Tam form görünümü: API Yapılandırması + Uygulama Tercihleri + Kaydet butonu | Sayfa yönlendirme |
| 5 | `_show_error(msg)` | 78-81 | Hata SnackBar | Hata durumları |
| 6 | `_show_success(msg)` | 83-86 | Başarı SnackBar | Başarılı işlemler |

### 5.2 Ayar Alanları

| Alan | Tip | Açıklama |
|------|-----|----------|
| `gemini_key_field` | TextField (password) | Gemini API Key |
| `whapi_token_field` | TextField (password) | Whapi Token |
| `whapi_url_field` | TextField | Whapi API URL (varsayılan: `https://gate.whapi.cloud`) |
| `refresh_interval_field` | TextField (number) | Otomatik yenileme süresi (saniye, varsayılan: 60) |

---

## 🔷 BÖLÜM 6: LOG İZLEME — `LogViewer` + `LogPage`

> **Dosya:** `src/gui/components/log_viewer.py` (183 satır)
> **Sınıflar:** `LogViewer`, `LogPage`

### 6.1 LogViewer (Canlı Dosya İzleyici)

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 1 | `__init__(log_path, height)` | 7-25 | Log dosya yolunu alır, ListView oluşturur, Container stilini ayarlar | Oluşturulma |
| 2 | `start_watch()` | 27-119 | **Canlı izleme döngüsü (2 sn):** Dosya boyut değişimini takip eder → yeni satırları okur → renk kodlaması (ERROR=kırmızı, WARNING=amber, SUCCESS=yeşil, INFO=mavi) → 500 satır buffer limiti | Sayfa açılışı |
| 3 | `stop_watch()` | 121-122 | İzlemeyi durdurur | Sayfa kapanışı |

### 6.2 LogPage (Log Sayfası)

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 4 | `__init__(page)` | 125-132 | İki ayrı log izleyici oluşturur: orchestrator + sistem | Uygulama başlangıcı |
| 5 | `get_view()` | 134-182 | İki bölümlü log sayfası: Orchestrator (Canlı Veri Akışı) + Uygulama Logları. Her iki izleyiciyi de başlatır | Sayfa yönlendirme |

### 6.3 İzlenen Log Dosyaları

| Log | Yol | İçerik |
|-----|-----|--------|
| Orchestrator | `tools/orchestrator.log` | Veri çekme ve işleme logları |
| Sistem | `logs/MaviLojistikGUI_{pid}.log` | Uygulama hata ve bilgi logları |

### 6.4 Renk Kodlama Sistemi

| Seviye | Anahtar Kelimeler | Renk |
|--------|-------------------|------|
| Hata | `ERROR`, `CRITICAL`, `[FAIL]` | `DANGER` (kırmızı) |
| Uyarı | `WARNING`, `[WARN]` | `WARNING` (amber) |
| Başarı | `SUCCESS`, `[OK]` | `SUCCESS` (yeşil) |
| Bilgi | `INFO`, `[INFO]` | `#64b5f6` (açık mavi) |
| Normal | Diğer | `white` |

---

## 🔶 BÖLÜM 7: TEMA VE STİLLER — `styles.py`

> **Dosya:** `src/gui/styles.py` (66 satır)
> **Sınıflar:** `AppColors`, `AppGradients`, `AppStyles`

### 7.1 Renk Paleti (`AppColors`)

| Sabit | Değer | Kullanım |
|-------|-------|----------|
| `BG_DEEP` | `#0a0f1e` | Ana arka plan |
| `SURFACE` | `#161c2e` | Panel/kart yüzeyi |
| `SURFACE_LIGHT` | `#1e293b` | Hover/alternatif yüzey |
| `PRIMARY` | `#3b82f6` | Electric Blue — ana vurgu rengi |
| `ACCENT` | `#00d2ff` | Cyan — ikincil vurgu |
| `TEXT` | `#f8fafc` | Ana metin (beyaz) |
| `TEXT_MUTED` | `#94a3b8` | Soluk metin (gri) |
| `SUCCESS` | `#10b981` | Emerald — başarı |
| `DANGER` | `#f43f5e` | Rose — hata/tehlike |
| `WARNING` | `#f59e0b` | Amber — uyarı |

### 7.2 Degradeler (`AppGradients`)

| Degrade | Renkler |
|---------|---------|
| `PRIMARY` | `#3b82f6` → `#1d4ed8` |
| `ACCENT` | `#00d2ff` → `#3b82f6` |
| `SURFACE` | `#161c2e` → `#111827` |

### 7.3 Stil Sabitleri (`AppStyles`)

| Sabit | Değer | Kullanım |
|-------|-------|----------|
| `CARD_SHADOW` | blur=15, spread=1, black26, offset(0,5) | Panel/kart gölgesi |
| `HEADER_TITLE` | size=24, bold, Segoe UI Semibold | Başlık text stili |

### 7.4 Tema Uygulama

| Fonksiyon | Satır | Açıklama |
|-----------|-------|----------|
| `apply_app_theme(page)` | 53-65 | Dark mode, renk şeması (primary/secondary/surface), Segoe UI font, COMFORTABLE density |

---

## ⚪ BÖLÜM 8: LEGACY BİLEŞENLER (Tkinter)

> Bu bileşenler Tkinter tabanlıdır ve **eski masaüstü uygulamadan (`masaustu_uygulama.py`) kalmıştır**. Flet arayüzünde aktif olarak kullanılmamaktadır.

### 8.1 `BlacklistManager` (managers.py, Satır 29-151)

| # | Metod | Açıklama |
|---|-------|----------|
| 1 | `open_window()` | Tkinter Toplevel pencere açar |
| 2 | `_setup_ui(parent)` | Entry + Listbox + Butonlar |
| 3 | `refresh_list()` | Listbox'ı yeniler |
| 4 | `add_number()` | Numara ekler (normalize + kontrol) |
| 5 | `remove_number()` | Seçili numaraları siler |
| 6 | `refresh_list_and_gui()` | Liste + parent GUI yeniler |

### 8.2 `GroupManager` (managers.py, Satır 152-517)

| # | Metod | Açıklama |
|---|-------|----------|
| 1 | `_startup_fetch()` | Arka plan thread'de API grupları çeker |
| 2 | `fetch_groups_from_api()` | WhatsApp API paginated çekim |
| 3 | `open_group_management()` | Tkinter pencere açar |
| 4 | `_setup_ui(parent)` | İki panelli Treeview arayüzü |
| 5 | `add_selected_group()` | API'den seçili grubu kaydeder |
| 6 | `delete_all_selected()` | Seçili grupları toplu siler |
| 7 | `on_tree_button_press/motion/release()` | Drag & Drop sürükle-bırak |
| 8 | `save_group_cache() / load_group_cache()` | Yerel JSON önbellek |
| 9 | `filter_api_groups()` | API listesini filtreler |
| 10 | `refresh_api_groups()` | API'den yeniden çeker |

### 8.3 `TagSelector` (tag_selector.py, 140 satır)

| # | Metod | Açıklama |
|---|-------|----------|
| 1 | `filter_suggestions()` | Türkçe uyumlu otomatik filtre |
| 2 | `add_tag_from_entry()` | Etiket ekler (duplicate kontrolü) |
| 3 | `render_tags()` | Etiketleri mavi kutular olarak gösterir |
| 4 | `remove_tag(value)` | Etiketi kaldırır |
| 5 | `get_values() / set_values() / clear()` | Veri get/set |

### 8.4 `AutocompleteEntry` (autocomplete.py, 73 satır)

| # | Metod | Açıklama |
|---|-------|----------|
| 1 | `handle_keyrelease()` | Tuş bırakıldığında filtreler |
| 2 | `handle_focus()` | Odak alındığında tam listeyi gösterir |
| 3 | `_match()` | Türkçe karakter toleranslı eşleşme |

---

## 📊 BÖLÜM 9: VERİ AKIŞ DİYAGRAMI

```
 ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 │  WhatsApp    │     │  Webhook     │     │  Yerel       │
 │  Grupları    │────▶│  Sunucusu    │────▶│  JSON        │
 │  (Mesajlar)  │     │  (FastAPI)   │     │  Depolama    │
 └──────────────┘     └──────────────┘     └──────┬───────┘
                                                   │
                                                   ▼
                                          ┌────────────────┐
                                          │AsyncDataService │
                                          │load_unprocessed│
                                          └────────┬───────┘
                                                   │
          ┌────────────────────────────────────────┼────────────────────┐
          │                                        │                    │
          ▼                                        ▼                    ▼
 ┌─────────────────┐               ┌─────────────────────┐  ┌──────────────┐
 │  OperationCenter │               │ ManagementCenter    │  │ ServerControl│
 │                  │               │                      │  │              │
 │ Sol: Mesaj Liste │               │ Tab0: Yük Tanımlama │  │ CPU/RAM/     │
 │ Orta: Sevkiyat   │               │ Tab1: Mahalle        │  │ Uptime       │
 │ Sağ: İstatistik  │               │ Tab2: Gruplar        │  │ Terminal     │
 │                  │               │ Tab3: Kara Liste     │  │ Kontroller   │
 │ ✅ Onayla        │               │ Tab4: Ayarlar        │  │              │
 │ ✏️ Düzenle       │               │                      │  │ Restart/Stop │
 │ 🗑️ Sil          │               │ CRUD İşlemleri       │  │ Start/Pull   │
 └────────┬─────────┘               └──────────────────────┘  └──────────────┘
          │
          ▼
 ┌─────────────────┐
 │ SubmissionQueue  │
 │ (Arka Plan)      │
 └────────┬─────────┘
          │
          ▼
 ┌──────────────┐
 │ YükBurada    │
 │ API (POST)   │
 └──────────────┘
```

---

## 📌 BÖLÜM 10: BUTON/AKSİYON HARİTASI (Kullanıcı Perspektifi)

### Sidebar Navigasyonu
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| Operasyon Merkezi | `change_page("Operasyon")` | Mesaj/sevkiyat yönetimi |
| Yönetim Paneli | `change_page("Yönetim")` | Veri tanımlama/yönetim |
| Sunucu Kontrolü | `change_page("Sunucu")` | Uzak sunucu kontrolü |
| Sistem Logları | `change_page("Loglar")` | Canlı log izleme |
| Ayarlar | `change_page("Ayarlar")` | Yönetim → Tab 5 |

### Operasyon Merkezi
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| ◀ / ▶ | `navigate_message(-1/+1)` | Mesaj navigasyonu |
| Mesaj Kartı | `_select_message(mid)` | Mesaj seçimi |
| 🔄 Yenile | `load_data()` | Veriyi yenile |
| Zaman Filtresi | `load_data()` | 10dk / 1saat / Bugün / Tümü |
| ✅ Onayla | `confirm_shipment(mid, idx)` | Sevkiyatı onayla |
| ✏️ Düzenle | `open_edit_dialog(mid, idx)` | Düzenleme dialogu |
| 🗑️ Sil | `delete_shipment(mid, idx)` | Sevkiyatı sil |
| SERVİSİ BAŞLAT | `start_service()` | Veri çekiciyi başlat |
| SERVİSİ DURDUR | `stop_service()` | Veri çekiciyi durdur |

### Düzenleme Dialogu
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| ⇅ Yer Değiştir | `_swap_locations()` | Nereden ↔ Nereye |
| 💾 KAYDET | `save_edit()` | Değişiklikleri kaydet |
| İptal | dialog.close | Dialogu kapat |

### Yönetim Merkezi — Yük Tanımlama
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| 🔍 Ara | `_filter_yuk()` | Tanım filtrele |
| TANIMI KAYDET | `_save_yuk_tanimi()` | Yeni tanım ekle |
| 🗑️ Sil | `_delete_yuk_tanimi()` | Tanım sil |
| 🔄 Yenile | `_load_yuk_data()` | Verileri yenile |

### Yönetim Merkezi — Mahalle
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| İl Dropdown | `_on_il_change()` | İl seç → ilçe filtrele |
| İlçe Dropdown | `_on_ilce_change()` | İlçe seç → mahalle listele |
| ➕ Mahalle Ekle | `_add_mahalle()` | Yeni mahalle |
| 🗑️ Sil | `_delete_mahalle()` | Mahalle sil |

### Yönetim Merkezi — Gruplar
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| ➕ Manuel Ekle | `_add_group()` | Ad + ID ile ekle |
| 🗑️ Sil | `_delete_group()` | Grubu kaldır |
| Grupları WhatsApp'tan Çek | `_fetch_whatsapp_groups()` | API'den çek |
| ➕ (Çekilen grup) | `_save_group()` | API grubunu kaydet |

### Yönetim Merkezi — Kara Liste
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| ➕ Ekle | `_add_blacklist()` | Numara engelle |
| 🗑️ Sil | `_delete_blacklist()` | Engeli kaldır |

### Sunucu Kontrolü
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| Yeniden Başlat | `_run_command("restart")` | Sunucu restart |
| Durdur | `_run_command("stop")` | Sunucu durdur |
| Başlat | `_run_command("start")` | Sunucu başlat |
| Kod Güncelle | `_run_command("pull")` | Git pull |
| 🔄 Log Yenile | `_refresh_logs()` | Logları çek |

### Ayarlar
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| AYARLARI KAYDET | `save_settings()` | .env + config kaydet |
| 🔄 Yenile | `load_settings()` | Mevcut ayarları yükle |

---

## ⚠️ BÖLÜM 11: BİLİNEN KISITLAMALAR VE NOTLAR

1. **Legacy Tkinter Bileşenleri:** `managers.py`, `tag_selector.py`, `autocomplete.py` dosyaları hala Tkinter tabanlıdır. Flet arayüzünde aktif olarak kullanılmaz, ancak importable durumdadır.
2. **Ayarlar Yönlendirmesi:** "Ayarlar" sidebar öğesi aslında Yönetim Merkezi'nin 5. sekmesine (index 4) yönlendirmedir, ayrı bir sayfa değildir.
3. **Otomatik Onay Yok:** Flet versiyonunda `masaustu_uygulama.py`'deki otomatik onay sistemi henüz taşınmamıştır.
4. **Duplicate Mahalle Fonksiyon:** `_setup_mahalle_sync()` (satır 243) ve `_setup_mahalle()` (satır 355) ikisi de aynı işlevi yapan fonksiyonlardır. `_setup_mahalle()` async versiyondur ama kullanılmamaktadır.
5. **Session Error Handling:** Tüm sayfalarda `page.update()` çağrıları session/destroyed hata kontrolü ile sarmalanmıştır.
6. **Filtre Dropdown Event:** `time_filter.on_select` kullanılmış — Flet versiyona bağlı olarak `on_change` gerekebilir.
7. **ServerControl Background Task:** `_update_status()` sonsuz döngüsü sayfa kapanınca durdurulmamaktadır.
8. **Log Buffer:** LogViewer 500 satır limitine sahiptir, eski loglar otomatik olarak kesilir.
9. **Kara Liste Normalizasyonu Yok:** Flet'teki `_add_blacklist()` metodu ham telefon numarasını kaydeder, `normalize_phone()` çağrısı yapılmaz.
10. **Canlı Yayındaki Yükler Yok:** `masaustu_uygulama.py`'deki `open_live_loads_window()` ve `refresh_live_loads()` fonksiyonları Flet'e taşınmamıştır.

---

## 📈 TOPLAM BİLEŞEN SAYISI

| Kategori | Dosya | Sınıf/Fonksiyon Sayısı | Metod Sayısı |
|----------|-------|------------------------|-------------|
| Ana Uygulama | `flet_app.py` | 5 fonksiyon | 5 |
| Operasyon Merkezi | `operation_center.py` | 1 sınıf | 22 |
| Yönetim Merkezi | `management_center.py` | 1 sınıf | 26 |
| Sunucu Kontrolü | `server_control.py` | 1 sınıf | 6 |
| Ayarlar | `settings_page.py` | 1 sınıf | 6 |
| Log İzleme | `log_viewer.py` | 2 sınıf | 5 |
| Stiller | `styles.py` | 3 sınıf + 1 fonksiyon | 4 |
| Legacy: Managers | `managers.py` | 2 sınıf (Tkinter) | ~25 |
| Legacy: Tag Selector | `tag_selector.py` | 1 sınıf (Tkinter) | 7 |
| Legacy: Autocomplete | `autocomplete.py` | 1 sınıf (Tkinter) | 3 |
| **TOPLAM** | **9 dosya** | **13 sınıf + 6 fonksiyon** | **~109** |

### Flet (Aktif) vs Legacy (Tkinter)

| Durum | Dosya Sayısı | Metod Sayısı |
|-------|-------------|-------------|
| ✅ Flet Aktif | 6 dosya | ~74 metod |
| ⚠️ Tkinter Legacy | 3 dosya | ~35 metod |

---

> 📝 **Not:** Bu belge, `flet_app.py` ve ilişkili 8 modülün (toplam ~3436 satır) kapsamlı analizi sonucunda oluşturulmuştur. Her metod satır numarası, tetikleyicisi ve bağımlılıkları ile birlikte listelenmiştir.
