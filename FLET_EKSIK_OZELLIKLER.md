# 🔍 FLET UYGULAMASINDA EKSİK ÖZELLİKLER

> **Karşılaştırma:** `masaustu_uygulama.py` (90 aksiyon) vs `flet_app.py` ekosistemi (~74 aktif metod)
> **Tarih:** 2026-04-21
> **Amaç:** Tkinter'da olup Flet'e taşınmamış tüm özellikler

---

## 📊 GENEL KARŞILAŞTIRMA TABLOSU

| Kategori | masaustu_uygulama.py | flet_app.py | Eksik |
|----------|---------------------|-------------|-------|
| Mesaj Yönetimi | 24 metod | 9 metod | **15** |
| Sevkiyat İşlemleri | 21 metod | 8 metod | **13** |
| Doğrulama | 3 metod | 0 metod | **3** |
| Servis Yönetimi | 8 metod | 2 metod | **6** |
| Görüntüleme | 15 metod | 2 metod | **13** |
| Form Bileşenleri | 6 metod | 0 (dialog var) | **5** |
| Konum Yönetimi | 8 metod | 2 metod | **6** |
| Yaşam Döngüsü | 5 metod | 1 metod | **4** |
| **TOPLAM** | **90** | **~24 eşdeğer** | **~65** |

---

## 🔴 KRİTİK EKSİKLER (İş Mantığı)

Bu özellikler uygulamanın temel işlevselliği için gereklidir.

### 1. OTOMATİK ONAY SİSTEMİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor | Öncelik |
|---|-------------------|-------|-----------|---------|
| 1 | `process_auto_approvals()` | 2632-2653 | Tüm mesajları tarar, otomatik onay kriterlerine uyan sevkiyatları onaylar | 🔴 Yüksek |
| 2 | `auto_approve_message(msg_data)` | 2655-2704 | Tek mesajı otomatik onaylar: kombinasyon üret → kuyruğa ekle → MongoDB kaydet → sessizce sil | 🔴 Yüksek |
| 3 | `_remove_message_by_id_silent(mid)` | 2706-2731 | UI yenilemesi yapmadan mesajı bellekten siler (otomatik onay desteği) | 🔴 Yüksek |

> **Etki:** Flet'te kullanıcı her sevkiyatı **tek tek elle onaylamak** zorunda. Otomatik mod yok.

### 2. MESAJ FİLTRELEME SİSTEMİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor | Öncelik |
|---|-------------------|-------|-----------|---------|
| 4 | `filter_messages_by_time()` | 1779-1861 | Kayar pencere filtresi: Son X dakika mesajlarını gösterir (max 60 dk) | 🔴 Yüksek |
| 5 | `filter_messages_in_last_minutes()` | 1757-1777 | Dakika penceresine göre datetime filtresi, en yeniden eskiye sıralama | 🟡 Orta |
| 6 | `reset_time_filter()` | 1933-1939 | Filtreyi varsayılan 60 dk'ya sıfırlar, otomatik moda döner | 🟡 Orta |
| 7 | `_on_minutes_filter_change()` | 1928-1931 | ComboBox değişiminde filtre tetikleyicisi | 🟡 Orta |
| 8 | `_get_message_datetime(msg)` | 1863-1910 | 4 farklı format desteği ile mesaj tarih/saat çıkarma | 🟡 Orta |
| 9 | `_get_entry_date(item)` | 2062-2100 | Mesajdan tarih bilgisi çıkarma (purge/temizlik için) | 🟡 Orta |

> **Not:** Flet'te `time_filter` dropdown'ı var (10dk/1saat/Bugün/Tümü) ama Tkinter'daki gelişmiş kayar pencere filtreleme, otomatik mod ve sıfırlama mekanizması yok.

### 3. DOĞRULAMA (VALİDASYON) SİSTEMİ ❌

> **Etki:** Flet'te sevkiyat onaylanırken **hiçbir doğrulama yapılmıyor.** Geçersiz konum, mükerrer kayıt veya eksik veri ile onay mümkün.

### 4. MESAJ SİLME MEKANİZMALARI ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor | Öncelik |
|---|-------------------|-------|-----------|---------|
| 13 | `quick_delete_message()` | 1744-1747 | **Onay sormadan** mesajı siler, sonraki mesaja geçer | 🟡 Orta |
| 14 | `delete_current_message()` | 2752-2755 | **Onay sorarak** (messagebox) mesajı siler | 🟢 Düşük |
| 15 | `_remove_message_by_id(mid, status_msg)` | 2757-2798 | ID ile bellekten, dosyadan ve MongoDB'den siler. `processed` olarak işaretler | 🔴 Yüksek |

> **Etki:** Flet'te sadece sevkiyat bazında silme var (`delete_shipment`). **Mesajın tamamını silme** butonu/fonksiyonu yok.

---

## 🟡 ORTA ÖNCELİKLİ EKSİKLER (Kullanıcı Deneyimi)

### 5. ÇOKLU SEVKİYAT DÜZENLEMESİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 16 | `edit_multiple_shipments()` | 1223-1345 | Seçili **tüm** sevkiyatlara ortak değişiklik uygular (boş alanlar atlanır) |
| 17 | `save_multiple_edit_changes()` | 1359-1408 | Çoklu düzenleme kaydetme |
| 18 | `restore_multiple_shipments()` | 1347-1357 | Çoklu yedeklerden geri yükleme |

> **Flet'te:** Düzenleme sadece tek sevkiyat bazında. Birden fazla sevkiyatı aynı anda düzenleme yok.

### 6. GERİ ALMA (UNDO) SİSTEMİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 19 | `restore_original_shipment()` | 1127-1136 | Düzenleme öncesi haline döner (yedekten geri yükleme) |
| 20 | `restore_multiple_shipments()` | 1347-1357 | Çoklu geri yükleme |

> **Flet'te:** Düzenleme dialogunda yedekleme/geri alma yok. Kaydet'e basıldığında orijinal veriler kaybolur.

### 7. SEVKİYAT TABLO YÖNETİMİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 21 | `on_table_click(event)` | 2438-2479 | Checkbox toggle (☐↔☑), satır seçimi, aktif satır işaretleme |
| 22 | `toggle_select_all_shipments()` | 2484-2500 | Tümünü seç/bırak toggle |
| 23 | `set_active_shipment(index)` | 2525-2535 | Aktif satır işaretleme |
| 24 | `reset_active_shipment()` | 2502-2504 | Aktif satır sıfırlama |
| 25 | `sort_shipments_by_time()` | 3178-3195 | Sevkiyatları zamana göre sıralama |

> **Flet'te:** Sevkiyat kartları listelenmiş ama **çoklu seçim**, **tümünü seç**, **sıralama** gibi özellikler yok. Her kartta bireysel aksiyon butonları var.

### 8. SEVKİYAT EKLEME ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 26 | `add_new_shipment()` | 3295-3465 | Boş form açar, TagSelector ile tip seçimi, doğrulama (isim+nereden+nereye zorunlu) |
| 27 | `save_new_shipment()` | 3401-3465 | Yeni sevkiyatı doğrular, normalize eder, kaydeder |

> **Flet'te:** Mevcut sevkiyatları düzenleme var ama **sıfırdan yeni sevkiyat ekleme** butonu/formu yok.

### 9. MOUSE SCROLL NAVİGASYONU ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 28 | `on_mouse_wheel_message(event)` | 2363-2373 | Mesaj metin alanında mouse tekerleği ile mesaj değiştirme |

> **Flet'te:** Sadece ◀/▶ butonları ile navigasyon, scroll ile mesaj değiştirme yok.

---

## 🟢 DÜŞÜK ÖNCELİKLİ EKSİKLER (Görüntüleme/Ek Özellikler)

### 10. CANLI İZLE PANELLERİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 29 | `setup_bottom_pane()` | 4002-4032 | Alt panelde son 50 dakikanın mesajları (Treeview) |
| 30 | `update_live_panel()` | 4034-4074 | Alt paneli güncel mesajlarla günceller |
| 31 | `on_live_msg_click()` | 4076-4078 | Tıklama ile mesajı ana panele yükleme |
| 32 | `on_live_msg_double_click()` | 4080-4081 | Çift tıklama ile mesaj yükleme |

> **Flet'te:** Alt panel ("Canlı İzle") tamamen yok.

### 11. CANLI YAYINDAKİ YÜKLER ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 33 | `open_live_loads_window()` | 3937-3999 | Ayrı pencerede YükBurada API'den yayındaki yükleri gösterir |
| 34 | `refresh_live_loads()` | 4092-4181 | Son 1 saatin canlı yüklerini çeker, tabloyu günceller |

> **Flet'te:** YükBurada üzerindeki canlı yükleri görüntüleme penceresi yok.

### 12. DETAY PANELLERİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 35 | `toggle_info_panel()` | 612-625 | Mesaj detay bilgilerini (Grup, Zaman, Gönderen, Numara) accordion olarak açar/kapatır |
| 36 | `show_approved_records()` | 1412-1531 | Onaylanan kayıtları yan panelde listeler (son 1 saat) |
| 37 | `show_parsed_records()` | 1533-1739 | Ayrıştırılmış tüm mesajları arama, filtreleme ile gösterir |

> **Flet'te:** `toggle_info_panel` kısmen mevcut (meta bilgiler gösteriliyor), ancak "Onaylanan Kayıtlar" ve "Ayrıştırılmış Mesajlar" görüntüleme sayfaları tamamen yok.

### 13. YAN PANEL SİSTEMİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 38 | `open_side_panel(title, width)` | 825-866 | Sağ tarafta yan panel açar (başlık, kapatma, resize) |
| 39 | `close_side_panel()` | 868-873 | Yan paneli kapatır |
| 40 | `_bind_side_panel_handle()` | 1997-2001 | Sürüklenebilir resize handle |
| 41 | `_start_side_panel_resize()` | 2003-2005 | Resize başlangıç noktası |
| 42 | `_perform_side_panel_resize()` | 2007-2012 | Sürükleme ile panel genişliği değiştirme (min 300-max 800) |

> **Flet'te:** Yan panel yerine AlertDialog kullanılıyor. Sürüklenebilir/resizable yan panel yok.

### 14. FORM BİLEŞENLERİ (GELİŞMİŞ) ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 43 | `create_autocomplete_field()` | 2810-3131 | Gelişmiş Autocomplete: inline tamamlama, Türkçe karakter, ok navigasyon, ilçe→il otomatik |
| 44 | `create_checkbox_field()` | 3133-3150 | Checkbox grubu (Araç/Kasa/Yük tipi) |
| 45 | `create_multi_destination_field()` | 3197-3293 | Çoklu destinasyon (Nereye) — dinamik ekleme/çıkarma |
| 46 | `parse_type_to_list(value)` | 3153-3159 | String/list→list çevirim (`,` veya `+` ayırıcı) |
| 47 | `format_type_list_to_string(value)` | 3161-3170 | List→unique string çevirim |

> **Flet'te:** Düzenleme dialogunda basit TextField + Dropdown var. Autocomplete, çoklu destinasyon ve tag seçici yok.

### 15. KONUM YÖNETİMİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 48 | `load_il_ilceler()` | 2015-2032 | İl/İlçe verilerini yükler |
| 49 | `get_ilce_list(il_name)` | 1071-1080 | İl adına göre ilçe listesi |
| 50 | `find_il_by_ilce(ilce_name)` | 1082-1103 | İlçe adından il bulma (ters arama) |
| 51 | `_normalize_il_name(il_name)` | 1105-1115 | İl ismi normalizasyonu |
| 52 | `_get_default_ilce(il_name)` | 1117-1125 | Varsayılan ilçe |
| 53 | `update_location_combos()` | 1205-1221 | İl değiştiğinde ilçe combo güncelleme |

> **Flet'te:** Düzenleme dialogunda il/ilçe basit TextField olarak var. Autocomplete, ters arama, normalizasyon ve dropdown bağlantısı yok.

### 16. SERVİS YÖNETİMİ (GELİŞMİŞ) ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 54 | `start_continuous_fetch()` | 3670-3681 | Sürekli dosya işleme döngüsü başlatma (15 sn) |
| 55 | `stop_continuous_fetch()` | 3683-3691 | Sürekli çekim durdurma |
| 56 | `_continuous_fetch_loop()` | 3693-3727 | Ana işlem döngüsü: parse → UI yenile → otomatik onay → 15 sn uyku |
| 57 | `toggle_veri_cekici()` | 3653-3658 | Başlat/Durdur toggle |
| 58 | `sync_whatsapp_messages()` | 3619-3651 | Son 3 saatin WhatsApp mesajlarını çekme |

> **Flet'te:** Basit subprocess start/stop var ama **sürekli çekim döngüsü**, **otomatik parse+onay pipeline** ve **WhatsApp senkronizasyonu** yok.

### 17. YAŞAM DÖNGÜSÜ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 59 | `on_closing()` | 4183-4198 | Kapanış temizliği: veri çekici durdur → webhook durdur → pencere yok et |
| 60 | `start_periodic_refresh()` | 352-384 | Her 15 saniyede otomatik arka plan yenileme |
| 61 | `_background_refresh_task()` | 3500-3508 | Thread içinde IO işlemleri |
| 62 | `_reset_ui_empty()` | 3602-3615 | Mesaj kalmadığında boş UI durumu |
| 63 | `get_submitter()` | 3926-3935 | YükBurada submitter lazy-init |

> **Flet'te:** `on_closing` temizliği yok (ciddi kaynak sızıntısı riski), periyodik yenileme yok.

### 18. SAAT GÜNCELLEMESİ ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 64 | `update_clock()` | 421-437 | Her 1 saniyede saat etiketini günceller |

### 19. YER DEĞİŞTİR (ANA EKRAN) ❌

| # | Metod (masaustu) | Satır | Ne Yapıyor |
|---|-------------------|-------|-----------|
| 65 | `swap_locations()` | 1183-1203 | Nereden/Nereye bilgilerini ana ekrandan karşılıklı değiştirir |

> **Flet'te:** Düzenleme dialogu **içinde** swap var (`_swap_locations`), ama ana ekrandan doğrudan swap yok.

---

## 📋 ÖNCELİK SIRALI ÖZET

### 🔴 Yüksek Öncelik (İş Mantığı Kırılması)
| # | Özellik | Etki |
|---|---------|------|
| 1 | **Otomatik Onay Sistemi** | Kullanıcı her şeyi elle onaylamak zorunda |
| 2 | **Doğrulama (Validasyon)** | Geçersiz/mükerrer veri onaylanabilir |
| 3 | **Mesaj Silme (Tam)** | Mesajın tamamı tek seferde silinemiyor |
| 4 | **_remove_message_by_id** | MongoDB + dosya + bellek senkron silme eksik |
| 5 | **Periyodik Yenileme** | Otomatik veri güncelleme yok |
| 6 | **Kapanış Temizliği** | Kaynak sızıntısı riski |

### 🟡 Orta Öncelik (Kullanıcı Deneyimi)
| # | Özellik | Etki |
|---|---------|------|
| 7 | **Çoklu Düzenleme** | Birden fazla sevkiyatı tek seferde güncelleyememe |
| 8 | **Geri Alma (Undo)** | Hatalı düzenleme geri alınamaz |
| 9 | **Yeni Sevkiyat Ekleme** | Mevcut mesaja sevkiyat eklenemez |
| 10 | **Gelişmiş Filtre** | Kayar pencere, otomatik mod, sıfırlama yok |
| 11 | **Tümünü Seç / Sıralama** | Toplu işlem kolaylığı yok |
| 12 | **Konum Autocomplete** | İl/İlçe ilişkili seçim yok |

### 🟢 Düşük Öncelik (Ek Özellikler)
| # | Özellik | Etki |
|---|---------|------|
| 13 | **Canlı İzle Paneli** | Son 50 dk mesaj akışı yok |
| 14 | **Canlı Yükler Penceresi** | YükBurada canlı yük izleme yok |
| 15 | **Onaylanan Kayıtlar Görüntüleme** | Geçmiş onaylar gözden geçirilemiyor |
| 16 | **Ayrıştırılmış Mesajlar** | Tüm ayrıştırılmış veri listelenemiyor |
| 17 | **Sürüklenebilir Yan Panel** | Esnek düzenleme alanı yok |
| 18 | **Çoklu Destinasyon** | Birden fazla "nereye" eklenemiyor |
| 19 | **Saat Göstergesi** | Anlık saat yok |

---

## 📈 SAYISAL ÖZET

```
masaustu_uygulama.py:  90 aksiyon
flet_app.py ekosistemi: ~74 metod (aktif)

Eşleşen (taşınmış):      ~25 aksiyon
Eksik (taşınmamış):       ~65 aksiyon
Flet'e özgü yeni:         ~49 metod (yönetim merkezi tabs, sunucu kontrol, log izleme)
```

### Taşınma Oranı (Özellik Bazında)

| Kategori | Oran | Durum |
|----------|------|-------|
| Mesaj Navigasyonu | ✅ %80 | İyi (prev/next/select var) |
| Sevkiyat Görüntüleme | ✅ %70 | Kart formatında taşınmış |
| Sevkiyat Düzenleme | 🟡 %40 | Tekli dialog var, çoklu/undo yok |
| Sevkiyat Onaylama | 🟡 %30 | Tekli onay var, otomatik/toplu yok |
| Filtre / Arama | 🟡 %30 | Basit dropdown var, gelişmiş yok |
| Doğrulama | ❌ %0 | Tamamen yok |
| Otomatik Onay | ❌ %0 | Tamamen yok |
| Canlı İzle | ❌ %0 | Tamamen yok |
| Yan Panel | ❌ %0 | Dialog ile kısmen ikame |
| Form Bileşenleri | ❌ %10 | Basit dialog, gelişmiş yok |

---

> 📝 **Not:** Yönetim Merkezi (yük tanımlama, mahalle, grup, kara liste), Sunucu Kontrolü ve Log İzleme sayfaları Flet'e **yeni eklenmiş** özelliklerdir ve masaustu_uygulama.py'de bu şekilde yapılandırılmamıştır. Bu belge sadece **masaustu'da olup Flet'te olmayan** özellikleri kapsar.
