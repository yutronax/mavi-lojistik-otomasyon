# 📋 MASAÜSTÜ UYGULAMA — ORJİNAL MESAJ AKSİYONLARI ANALİZİ

> **Dosya:** `src/gui/masaustu_uygulama.py`
> **Toplam Satır:** 4206
> **Sınıf:** `LojistikYonetimGUI`
> **Son Analiz Tarihi:** 2026-04-21

Bu belge, masaüstü uygulamanın (LojistikYonetimGUI) orijinal mesaj üzerinden gerçekleştirebildiği **tüm aksiyonları**, **metod haritasını** ve **veri akışını** kapsamlı olarak belgelemektedir.

---

## 📐 MİMARİ GENEL BAKIŞ

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LojistikYonetimGUI (4206 satır)                 │
├──────────────┬──────────────┬────────────┬──────────┬──────────────┤
│  SOL PANEL   │  ORTA PANEL  │ SAĞ PANEL  │ YAN PANEL│  ALT PANEL   │
│ Orijinal     │  Sevkiyat    │  İşlemler  │ Düzenleme│  Canlı İzle  │
│ Mesaj        │  Tablosu     │  Butonları │ Formu    │  (Son 50 dk) │
├──────────────┴──────────────┴────────────┴──────────┴──────────────┤
│                        DURUM ÇUBUĞU                                │
└────────────────────────────────────────────────────────────────────┘
```

### Veri Katmanları
| Katman | Dosya/Servis | Açıklama |
|--------|-------------|----------|
| `DataService` | `src/services/data_service.py` | Yerel JSON dosya işlemleri, CRUD |
| `MongoDataService` | `src/services/mongo_service.py` | MongoDB senkronizasyonu (blacklist, gruplar) |
| `SubmissionQueue` | `src/services/submission_queue.py` | Arka plan gönderim kuyruğu |
| `YukBuradaSubmitter` | `tools/submit_approved_loads.py` | YükBurada API iletişimi |
| `LocationHelper` | `src/utils/location_helper.py` | İl/İlçe/Mahalle doğrulama |

---

## 🔵 BÖLÜM 1: MESAJ YÖNETİMİ AKSİYONLARI

### 1.1 Mesaj Yükleme ve Navigasyon

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 1 | `load_messages_from_file()` | 2144-2250 | Tüm mesajları `unprocessed_data` sözlüğünden okur, blacklist filtresi uygular, geçersiz konum kontrolü yapar, `all_messages[]` listesini oluşturur | Başlangıç + Yenileme |
| 2 | `load_message_at_index(index)` | 2252-2344 | Belirtilen indeksteki mesajı yükler, sol panelde orijinal metni gösterir, orta panelde sevkiyat tablosunu doldurur, sayaçları günceller | İndex değiştiğinde |
| 3 | `load_next_message()` | 2346-2348 | Bir sonraki mesaja geçer (`current_message_index + 1`) | ▶ butonu |
| 4 | `load_previous_message()` | 2350-2352 | Bir önceki mesaja geçer (`current_message_index - 1`) | ◀ butonu |
| 5 | `prev_message()` | 2355-2357 | `load_previous_message()` alias'ı | Sol panel ◀ butonu |
| 6 | `next_message()` | 2359-2361 | `load_next_message()` alias'ı | Sol panel ▶ butonu |
| 7 | `on_mouse_wheel_message(event)` | 2363-2373 | Mouse tekerleği ile mesaj değiştirme (yukarı=önceki, aşağı=sonraki) | Mesaj metin alanında scroll |

### 1.2 Mesaj Filtreleme

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 8 | `filter_messages_by_time()` | 1779-1861 | Kayar pencere filtresi: Son X dakika içindeki mesajları gösterir (max 60 dk) | Filtrele butonu / Otomatik |
| 9 | `filter_messages_in_last_minutes()` | 1757-1777 | Belirtilen dakika penceresindeki mesajları datetime nesnesine göre filtreler, en yeniden en eskiye sıralar | `filter_messages_by_time` tarafından |
| 10 | `reset_time_filter()` | 1933-1939 | Filtreyi varsayılan 60 dakikaya sıfırlar, otomatik moda döner | ↻ Sıfırla butonu |
| 11 | `_on_minutes_filter_change()` | 1928-1931 | Dakika ComboBox değiştiğinde filtreyi tetikler | ComboBox seçimi |
| 12 | `_get_message_datetime(msg)` | 1863-1910 | Mesajın tarih/saat bilgisini çıkarır (4 farklı format desteği: Unix timestamp, ISO, readable string, time_str) | Tüm filtreleme işlemleri |
| 13 | `_get_entry_date(item)` | 2062-2100 | Mesajdan tarih (date) bilgisi çıkarır (purge için) | DataService |

### 1.3 Mesaj Silme

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 14 | `quick_delete_message()` | 1744-1747 | **Onay sormadan** mesajı siler ve sonraki mesaja geçer | 🗑️ HIZLI SİL butonu |
| 15 | `delete_current_message()` | 2752-2755 | **Onay sorarak** (messagebox) mesajı siler | — (şu an butonu yok) |
| 16 | `_remove_message_by_id(mid, status_msg)` | 2757-2798 | Mesajı ID ile bellekten, dosyadan ve MongoDB'den siler. İçeriği `processed` olarak işaretler. Sonraki mesajı yükler | Tüm silme işlemleri |
| 17 | `_remove_message_by_id_silent(mid)` | 2706-2731 | UI yenilemesi yapmadan mesajı bellekten siler (oto-onay için) | Otomatik onay sistemi |

### 1.4 Mesaj Yenileme ve Senkronizasyon

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 18 | `manual_refresh()` | 3472-3498 | Manuel yenileme — arka plan thread'inde çalışır, mevcut pozisyonu korur | 🔄 YENİLE butonu |
| 19 | `refresh_messages()` | 3517-3600 | Ana yenileme metodu: disk'ten yeniden okur, filtre uygular, mevcut mesaj ID'si ile pozisyon korur | Manuel + Periyodik |
| 20 | `start_periodic_refresh()` | 352-384 | Her 15 saniyede arka plan thread'inde otomatik yenileme | Uygulama başlangıcı |
| 21 | `_background_refresh_task()` | 3500-3508 | Thread içinde IO işlemlerini gerçekleştirir | `manual_refresh` |
| 22 | `sync_whatsapp_messages()` | 3619-3651 | WhatsApp API üzerinden son 3 saatin mesajlarını çeker | WhatsApp senkronize butonu |
| 23 | `load_unprocessed_parsed_data()` | 2102-2111 | `DataService` aracılığıyla yerel depodan mesajları yükler | Başlangıç + Yenileme |
| 24 | `save_unprocessed_data()` | 2113-2142 | `DataService` aracılığıyla mesajları atomik olarak kaydeder | Her veri değişikliğinde |

---

## 🟢 BÖLÜM 2: SEVKİYAT AKSİYONLARI

### 2.1 Sevkiyat Onaylama

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 25 | `approve_shipment()` | 2550-2625 | **Seçili sevkiyatları onaylar:** Araç-Kasa kombinasyonları üretir → `SubmissionQueue`'ya ekler → `onaylananlar.json`'a yazar → Listeden siler. Tüm sevkiyatlar onaylanırsa mesaj tamamen kaldırılır | ✅ ONAYLA butonu |
| 26 | `process_auto_approvals()` | 2632-2653 | **Otomatik Onay:** Tüm mesajları tarar ve tek tek `auto_approve_message` ile onaylar | Otomatik onay checkbox aktif iken |
| 27 | `auto_approve_message(msg_data)` | 2655-2704 | Belirli bir mesajı otomatik olarak onaylar: kombinasyon üretir → kuyruğa ekler → MongoDB'ye kaydeder → mesajı sessizce siler | `process_auto_approvals` |

### 2.2 Sevkiyat Düzenleme

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 28 | `toggle_edit_mode()` | 3172-3176 | Seçili sevkiyat sayısına göre tekli veya çoklu düzenleme açar | ✏️ DÜZENLE butonu |
| 29 | `edit_selected_shipment()` | 877-1069 | **Tekli Düzenleme:** Yan panelde form açar — Firma adı, İl/İlçe (autocomplete), Araç/Kasa/Yük tipi (TagSelector), Telefon, Fiyat, Açıklama alanlarını düzenler. Yedek alır (geri alma için) | Çift tıklama / Düzenle butonu |
| 30 | `edit_multiple_shipments()` | 1223-1345 | **Çoklu Düzenleme:** Seçili tüm sevkiyatlara ortak değişiklik uygular. Sadece dolu alanlar güncellenir (boş alanlar atlanır) | 2+ sevkiyat seçiliyken Düzenle |
| 31 | `save_edit_changes()` | 1138-1181 | Düzenleme formundaki değişiklikleri kaydeder, normalize eder (İl/İlçe, telefon temizleme, fiyat boşsa "Sorunuz") | 💾 KAYDET butonu |
| 32 | `save_multiple_edit_changes()` | 1359-1408 | Çoklu düzenleme değişikliklerini tüm seçili sevkiyatlara uygular | 💾 TÜMÜNÜ GÜNCELLE butonu |
| 33 | `restore_original_shipment()` | 1127-1136 | Yedekten geri yükleme — düzenleme öncesi haline döner | ↩️ Geri Al butonu |
| 34 | `restore_multiple_shipments()` | 1347-1357 | Çoklu yedeklerden geri yükleme | ↩️ Geri Al butonu (çoklu) |
| 35 | `swap_locations()` | 1183-1203 | Nereden/Nereye bilgilerini karşılıklı değiştirir | 🔄 Yer Değiştir butonu |

### 2.3 Sevkiyat Ekleme ve Silme

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 36 | `add_new_shipment()` | 3295-3465 | **Yeni Sevkiyat Ekleme:** Boş form açar, TagSelector ile tip seçimi, varsayılan kasa AÇIK/KAPALI, doğrulama (isim + nereden + nereye zorunlu) | ➕ EKLE butonu |
| 37 | `save_new_shipment()` | 3401-3465 | Yeni sevkiyatı doğrular ve kaydeder: form verilerini toplar → normalize eder → `unprocessed_data`'ya ekler → dosyaya yazar → tabloyu günceller | 💾 KAYDET butonu (ekleme formu) |
| 38 | `delete_selected_shipment()` | 2733-2750 | Seçili sevkiyatları siler. Tüm sevkiyatlar silinirse mesaj da kaldırılır | 🗑️ SİL butonu |

### 2.4 Sevkiyat Tablo Yönetimi

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 39 | `update_shipment_list()` | 2375-2436 | Tablo görünümünü yeniler: seçimleri ve aktif satırı korur, zebra efekti uygular, sayaç günceller | Her veri değişikliğinde |
| 40 | `on_table_click(event)` | 2438-2479 | Tabloda tıklama: checkbox toggle (☐↔☑), satır seçimi, aktif satır işaretleme | Tablo tıklama |
| 41 | `on_cell_double_click(event)` | 2481-2482 | Çift tıklama ile düzenleme moduna geçer | Tablo çift tıklama |
| 42 | `toggle_select_all_shipments()` | 2484-2500 | Tüm sevkiyatları seç/bırak toggle'ı | ☐ başlık tıklama |
| 43 | `set_active_shipment(index)` | 2525-2535 | Belirtilen indexi aktif satır olarak işaretler | Tıklama sonrası |
| 44 | `reset_active_shipment()` | 2502-2504 | Aktif satır işaretini sıfırlar | Mesaj değiştiğinde |
| 45 | `sort_shipments_by_time()` | 3178-3195 | Sevkiyatları oluşturulma zamanına göre sıralar (en yeni üstte) | Filtre sonrası |

---

## 🟡 BÖLÜM 3: DOĞRULAMA (VALİDASYON) AKSİYONLARI

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 46 | `validate_shipment_data()` | 3820-3852 | `Shipment` modeli ile sevkiyat verisi doğrulama (is_valid, error_message döner) | Onay öncesi |
| 47 | `check_duplicate_shipment()` | 3854-3902 | Mükerrer kontrol: aynı telefon + aynı güzergah = mükerrer | Onay öncesi |
| 48 | `validate_location(il, ilce)` | 3904-3922 | İl/İlçe kombinasyonunu `il_ilceler.json` ile doğrular | Form kayıt |

---

## 🟣 BÖLÜM 4: SERVİS YÖNETİMİ AKSİYONLARI

### 4.1 Veri Çekici Servisi (Webhook + Orkestratör)

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 49 | `start_veri_cekici()` | 3728-3754 | **Ana Servis Başlatma:** Continuous fetch loop + Webhook sunucusu başlatır | Otomatik (1 sn sonra) |
| 50 | `stop_veri_cekici()` | 3756-3788 | Tüm arka plan servislerini durdurur: fetch loop + webhook + ngrok.exe temizliği | — (şu an butonu yok) |
| 51 | `toggle_veri_cekici()` | 3653-3658 | Başlat/Durdur toggle'ı | — |
| 52 | `start_continuous_fetch()` | 3670-3681 | Arka plan thread'inde sürekli yerel dosya işleme döngüsü başlatır (15 sn aralık) | `start_veri_cekici` |
| 53 | `stop_continuous_fetch()` | 3683-3691 | Sürekli çekim döngüsünü durdurur | `stop_veri_cekici` |
| 54 | `_continuous_fetch_loop()` | 3693-3727 | **Ana İşlem Döngüsü:** `process_unprocessed_messages()` → UI yenileme → otomatik onay kontrolü → 15 sn uyku | Thread içinde |
| 55 | `launch_parser_in_terminal()` | 803-806 | Thread modunda veri çekiciyi başlatır (alias) | — |

### 4.2 WhatsApp Senkronizasyonu

| # | Metod | Satır | Açıklama |
|---|-------|-------|----------|
| 56 | `sync_whatsapp_messages()` | 3619-3651 | Son 3 saatin WhatsApp mesajlarını çeker (sadece kayıtlı gruplar), kuyruğa aktarır |

---

## 🔴 BÖLÜM 5: GÖRÜNTÜLEMEYEİLGİLİ AKSİYONLAR

### 5.1 Yan Panel Yönetimi

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 57 | `open_side_panel(title, width)` | 825-866 | Sağ tarafta yan panel açar — başlık, kapatma butonu, dinamik resize handle | Düzenleme/Onaylanan kayıtlar |
| 58 | `close_side_panel()` | 868-873 | Yan paneli kapatır (pack_forget) | ✖ butonu / Mesaj değişimi |
| 59 | `_bind_side_panel_handle()` | 1997-2001 | Sürüklenebilir resize handle bağlar | Panel açıldığında |
| 60 | `_start_side_panel_resize()` | 2003-2005 | Resize başlangıç noktasını yakalar | MousePress |
| 61 | `_perform_side_panel_resize()` | 2007-2012 | Sürükleme ile panel genişliğini değiştirir (min 300, max 800 px) | MouseDrag |

### 5.2 Detay Paneli

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 62 | `toggle_info_panel()` | 612-625 | Mesaj detay bilgilerini (Grup, Zaman, Gönderen, Numara) açar/kapatır (accordion stil) | ℹ️ Detaylar butonu |
| 63 | `show_approved_records()` | 1412-1531 | Onaylanan kayıtları yan panelde listeler — son 1 saat filtreli, Treeview + detay alanı | — |
| 64 | `show_parsed_records()` | 1533-1739 | Ayrıştırılmış tüm mesajları gösterir — arama, filtreleme, detaylı sevkiyat bilgisi, istatistikler | — |

### 5.3 Canlı İzle Panelleri

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 65 | `setup_bottom_pane()` | 4002-4032 | Alt paneli oluşturur: son 50 dakikanın mesajları, Treeview formatında | Başlangıç |
| 66 | `update_live_panel()` | 4034-4074 | Alt paneli son 50 dakikanın mesajlarıyla günceller, tıklanabilir linkler | Yenileme sonrası |
| 67 | `on_live_msg_click()` | 4076-4078 | Alt panelde mesaja tıklama → ana görüntüleyiciye yükleme | Tıklama |
| 68 | `on_live_msg_double_click()` | 4080-4081 | Çift tıklama ile mesaj yükleme | Çift tıklama |
| 69 | `open_live_loads_window()` | 3937-3999 | **Canlı Yayındaki Yükler:** Ayrı pencerede YükBurada API'den yayındaki yükleri gösterir | 📡 CANLI YÜKLER butonu |
| 70 | `refresh_live_loads()` | 4092-4181 | YükBurada API'den canlı yükleri çeker (son 1 saat), tabloyu günceller | Yenile butonu |

### 5.4 Yönetim Merkezi

| # | Metod | Satır | Açıklama | Tetikleyici |
|---|-------|-------|----------|-------------|
| 71 | `open_management_center(tab)` | 394-418 | Yönetim Merkezi penceresini açar (gruplar, blacklist sekmeleri) | — |

---

## 🟠 BÖLÜM 6: FORM BİLEŞENLERİ (UI Helper'lar)

| # | Metod | Satır | Açıklama |
|---|-------|-------|----------|
| 72 | `create_form_field()` | 2800-2808 | Basit metin giriş alanı oluşturur (Label + Entry) |
| 73 | `create_autocomplete_field()` | 2810-3131 | **Gelişmiş Autocomplete:** Entry + Listbox, inline tamamlama, Türkçe karakter desteği, yukarı/aşağı ok navigasyon, Enter ile seçim, ilçe→il otomatik doldurma |
| 74 | `create_checkbox_field()` | 3133-3150 | Checkbox grubu oluşturur (Araç/Kasa/Yük tipi seçimi) |
| 75 | `create_multi_destination_field()` | 3197-3293 | Çoklu destinasyon (Nereye) seçim alanı — ekleme/çıkarma butonları ile dinamik liste |
| 76 | `parse_type_to_list(value)` | 3153-3159 | String/list değeri listeye çevirir (`,` veya `+` ayırıcılarla) |
| 77 | `format_type_list_to_string(value)` | 3161-3170 | List değeri tekil (unique), ` - ` ile ayrılmış string'e çevirir |

---

## 🔷 BÖLÜM 7: KONUM YÖNETİMİ

| # | Metod | Satır | Açıklama |
|---|-------|-------|----------|
| 78 | `load_il_ilceler()` | 2015-2032 | `il_ilceler.json` dosyasını yükler |
| 79 | `get_ilce_list(il_name)` | 1071-1080 | İl adına göre ilçe listesini döndürür (case-insensitive) |
| 80 | `find_il_by_ilce(ilce_name)` | 1082-1103 | İlçe adından il'i bulur (ters arama) — tek eşleşme olmalı |
| 81 | `_normalize_il_name(il_name)` | 1105-1115 | İl ismini JSON'daki orijinal formata normalize eder |
| 82 | `_get_default_ilce(il_name)` | 1117-1125 | İl için varsayılan ilçeyi döndürür (`varsayılan_ilçe` alanından) |
| 83 | `update_location_combos()` | 1205-1221 | İl değiştiğinde ilçe combobox'ını günceller |
| 84 | `load_yuk_tipi()` | 2033-2046 | Yük tipi verilerini yükler |
| 85 | `load_arac_yuk_kasa_tipleri()` | 2047-2060 | Araç/Kasa/Yük tipi konfigürasyonunu yükler |

---

## 🔶 BÖLÜM 8: YAŞAM DÖNGÜSÜ AKSİYONLARI

| # | Metod | Satır | Açıklama |
|---|-------|-------|----------|
| 86 | `__init__()` | 93-350 | **Başlatma Sırası:** Renk/Font tanım → DataService → MongoDB bağlantısı → Veri yapıları → SubmissionQueue → Eski veri temizliği (purge) → UI kurulumu → Mesajları yükle → Filtre uygula → Webhook/Orkestratör başlat → Periyodik yenileme başlat |
| 87 | `on_closing()` | 4183-4198 | **Kapanış Temizliği:** Veri çekiciyi durdur → Webhook sunucuyu durdur → Pencereyi yok et |
| 88 | `update_clock()` | 421-437 | Her 1 saniyede saat etiketini günceller |
| 89 | `_reset_ui_empty()` | 3602-3615 | Mesaj kalmadığında UI'ı boş duruma getirir |
| 90 | `get_submitter()` | 3926-3935 | YükBurada göndericiyi lazy-initialize eder |

---

## 📊 BÖLÜM 9: VERİ AKIŞ DİYAGRAMI

```
 ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 │  WhatsApp    │     │  Webhook     │     │  Yerel       │
 │  Grupları    │────▶│  Sunucusu    │────▶│  JSON        │
 │  (Mesajlar)  │     │  (port 8080) │     │  Depolama    │
 └──────────────┘     └──────────────┘     └──────┬───────┘
                                                   │
                                                   ▼
                                          ┌────────────────┐
                                          │ DataService    │
                                          │ load_unprocsd()│
                                          └────────┬───────┘
                                                   │
                                                   ▼
 ┌──────────────────────────────────────────────────────────┐
 │               LojistikYonetimGUI                        │
 │                                                          │
 │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
 │  │ Filtre  │─▶│ Mesaj    │─▶│ Sevkiyat │─▶│ Tablo    │ │
 │  │ (Zaman) │  │ Yükleme  │  │ Çıkarma  │  │ Güncelle │ │
 │  └─────────┘  └──────────┘  └──────────┘  └──────────┘ │
 │                                                          │
 │  ┌──────────────────────────────────────────────────┐   │
 │  │              AKSİYON BUTONLARI                   │   │
 │  │                                                    │   │
 │  │  ✅ ONAYLA  │  🗑️ SİL  │  ✏️ DÜZENLE  │  ➕ EKLE │   │
 │  └──────┬───────────┬──────────┬──────────────┬─────┘   │
 │         │           │          │              │          │
 └─────────┼───────────┼──────────┼──────────────┼──────────┘
           │           │          │              │
           ▼           ▼          ▼              ▼
 ┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
 │ Submission   │ │ Mesajı   │ │ Yan Panel│ │ Yeni     │
 │ Queue        │ │ Kaldır   │ │ Düzenleme│ │ Sevkiyat │
 │ (Arka Plan)  │ │ + Kaydet │ │ Formu    │ │ Formu    │
 └──────┬───────┘ └──────────┘ └──────────┘ └──────────┘
        │
        ▼
 ┌──────────────┐
 │ YükBurada    │
 │ API          │
 │ (POST)       │
 └──────────────┘
```

---

## 📌 BÖLÜM 10: BUTON/AKSİYON HARİTASI (Kullanıcı Perspektifi)

### Üst Filtre Çubuğu
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| 🔍 Filtrele | `filter_messages_by_time()` | Son X dakikayı filtreler |
| ↻ Sıfırla | `reset_time_filter()` | Filtreyi 60 dk'ya döndürür |
| 📡 CANLI YAYINDAKİ YÜKLER | `open_live_loads_window()` | YükBurada canlı yük penceresi |

### Sol Panel (Orijinal Mesaj)
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| ◀ | `prev_message()` | Önceki mesaj |
| ▶ | `next_message()` | Sonraki mesaj |
| ℹ️ Detaylar ▼ | `toggle_info_panel()` | Mesaj detaylarını aç/kapat |
| 🖱️ Scroll | `on_mouse_wheel_message()` | Tekerlek ile mesaj değiştir |

### Orta Panel (Sevkiyat Tablosu)
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| ✅ ONAYLA | `approve_shipment()` | Seçili sevkiyatları onayla |
| 🗑️ SİL | `delete_selected_shipment()` | Seçili sevkiyatları sil |
| ✏️ DÜZENLE | `toggle_edit_mode()` | Tekli/çoklu düzenleme |
| ➕ EKLE | `add_new_shipment()` | Yeni sevkiyat ekle |
| ☐ Başlık | `toggle_select_all_shipments()` | Tümünü seç/bırak |
| Çift Tıklama | `on_cell_double_click()` | Hızlı düzenleme |

### Sağ Panel (İşlemler)
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| 🤖 OTOMATİK ONAY | `auto_approval_var` toggle | Otomatik onay açık/kapalı |
| 🗑️ HIZLI SİL | `quick_delete_message()` | Onaysız mesaj silme |
| 🔄 YENİLE | `manual_refresh()` | Manuel yenileme |
| ◀ / ▶ (alt) | `load_previous/next_message()` | Mesaj navigasyonu |

### Alt Panel (Canlı İzle)
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| Tıklama | `on_live_msg_click()` | Mesajı ana panele yükle |
| Çift Tıklama | `on_live_msg_double_click()` | Mesajı ana panele yükle |

### Yan Panel (Düzenleme Formu)
| Buton | Fonksiyon | Açıklama |
|-------|-----------|----------|
| 💾 KAYDET | `save_edit_changes()` | Değişiklikleri kaydet |
| ↩️ Geri Al | `restore_original_shipment()` | Yedekten geri yükle |
| 🔄 Yer Değiştir | `swap_locations()` | Nereden ↔ Nereye |
| ✖ | `close_side_panel()` | Paneli kapat |

---

## ⚠️ BÖLÜM 11: BİLİNEN KISITLAMALAR VE NOTLAR

1. **`google.generativeai` Deprecated:** Build sırasında `FutureWarning` çıkıyor. `google.genai` paketine geçiş planlanmalı.
2. **`src.utils.file_ops` Eksik:** Hidden import hatası — bu modül projede mevcut değil.
3. **Thread Safety:** UI güncellemeleri `root.after(0, ...)` ile ana thread'e taşınmış durumda, ancak bazı kenar durumları var.
4. **Otomatik Onay:** `process_auto_approvals()` tüm mesajları birden onaylıyor — filtreleme veya kalite kontrolü yok.
5. **delete_current_message():** Bu metod var ama arayüzde butonu bağlı değil.
6. **show_approved_records() / show_parsed_records():** Bu metodlar var ama arayüzde butonları bağlı değil.
7. **Çoklu Destinasyon:** `create_multi_destination_field()` metodu var ama hiçbir aksiyonda kullanılmıyor.
8. **MongoDB Senkronizasyonu:** `start_mongo_sync()` metodu boş bırakılmış (pass).

---

## 📈 TOPLAM AKSİYON SAYISI

| Kategori | Sayı |
|----------|------|
| Mesaj Yönetimi | 24 |
| Sevkiyat İşlemleri | 21 |
| Doğrulama | 3 |
| Servis Yönetimi | 8 |
| Görüntüleme | 15 |
| Form Bileşenleri | 6 |
| Konum Yönetimi | 8 |
| Yaşam Döngüsü | 5 |
| **TOPLAM** | **90** |

---

> 📝 **Not:** Bu belge, `masaustu_uygulama.py` dosyasının 4206 satırlık tam analizi sonucunda oluşturulmuştur. Her metod satır numarası ve bağımlılıkları ile birlikte listelenmiştir.
