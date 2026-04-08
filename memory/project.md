# Mavi Lojistik Otomasyonu - Proje Hafızası

## Proje Amacı
WhatsApp üzerinden gelen lojistik mesajlarını (yük ilanları) otomatik olarak toplamak, AI (Gemini) ile ayrıştırmak, şehir/ilçe doğrulaması yapmak ve bir yönetim paneli üzerinden bu ilanları onaylayıp çeşitli platformlara (örn: YükBurada) göndermek.

## Sistem Mimarisi
- **Frontend:** Flet (Python tabanlı Flutter framework) - *Migrasyon tamamlandı.*
- **Backend:** Asenkron Python (Asyncio)
- **Veri:** Yerel JSON (DataService + PersistenceManager üzerinden yönetilir)
- **Persistence:** Non-blocking Arka Plan Yazma Kuyruğu (PersistenceManager) - *Yeni mimari.*
- **AI:** Google Gemini (Mesaj ayrıştırma)
l tabanlı regex.
- **Veri Depolama:** Hibrit (Yerel JSON + Opsiyonel MongoDB).
- **Entegrasyon:** WhatsApp (Whapi.cloud), Webhook desteği, Canlı grup senkronizasyonu.
- **Otomatik Onay:** Yeni gelen ilanların kriterlere göre manuel müdahale olmadan otomatik onaylanması ve kuyruğa gönderilmesi.

## Teknolojiler
- **Dil:** Python 3.x
- **GUI:** Flet (0.82.2)
- **AI:** Google Generative AI (Gemini 1.5/2.0)
- **Veritabanı:** MongoDB (Pymongo), JSON
- **Network:** Requests, FastAPI (Webhook)

## Klasör Yapısı
- `src/gui/`: Flet arayüz dosyaları (`flet_app.py`, `pages/`, `components/`).
- `src/services/`: Veri yönetimi, API servisleri, kuyruk yönetimi.
- `src/parsers/`: Mesajları ayrıştıran AI/Regex modülleri.
- `src/api/`: Webhook sunucusu.
- `src/utils/`: Yardımcı araçlar (konum doğrulama, telefon normalizasyonu vb.).
- `data/`: Konum ve yük tanımlama verileri (JSON).
- `memory/`: Proje hafızası ve loglar.

## Kritik Dosyalar
- `src/gui/flet_app.py`: Ana giriş noktası ve Sidebar yönetimi.
- `src/services/persistence_manager.py`: Tüm dosya I/O işlemlerini arka planda kuyruğa alan, kilitlenme önleyici servis.
- `src/services/data_service.py`: Merkezi veri katmanı (PersistenceManager entegrasyonlu).
- `src/parsers/veri_cekici_ayristirici.py`: Ana orkestrasyon ve ayrıştırma motoru.
- `text_gen_parser.py`: Gemini tabanlı gelişmiş ayrıştırma mantığı (konteks tabanlı).
- `vps_main.py`: Headless (ekransız) modda 24/7 otonom çalışma motoru.
