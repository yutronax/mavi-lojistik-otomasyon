# Mavi Lojistik Otomasyonu - Proje Hafızası

## Proje Amacı
WhatsApp üzerinden gelen lojistik mesajlarını (yük ilanları) otomatik olarak toplamak, AI (Gemini) ile ayrıştırmak, şehir/ilçe doğrulaması yapmak ve bir yönetim paneli üzerinden bu ilanları onaylayıp çeşitli platformlara (örn: YükBurada) göndermek.

## Sistem Mimarisi
- **Frontend:** Flet (Python tabanlı Flutter framework) - *Migrasyon tamamlandı.*
- **Backend:** Asenkron Python (Asyncio)
- **Veri:** Yerel JSON (DataService + PersistenceManager üzerinden yönetilir)
- **Persistence:** Non-blocking Arka Plan Yazma Kuyruğu (PersistenceManager) - *Yeni mimari.*
- **AI:** Google Gemini (Primary), Groq Llama 3.3 (Fallback).
- **Spend Tracking:** AI kullanım maliyetlerini takip eden ve `data/ai_spend_history.json` dosyasında saklayan kalıcı sistem.
- **Location Validation:** Şehir/İlçe/Mahalle hiyerarşisiyle çalışan, 'Kemalpaşa' gibi tuzak konumları ve İstanbul yakalarını (Avrupa/Anadolu) otomatik düzelten validator.
- **Veri Depolama:** Hibrit (Yerel JSON + Opsiyonel MongoDB).
- **Entegrasyon:** WhatsApp (Whapi.cloud), Webhook desteği, Canlı grup senkronizasyonu.
- **Otomatik Onay:** Yeni gelen ilanlerin kriterlere göre manuel müdahale olmadan otomatik onaylanması ve kuyruğa gönderilmesi.
- **Güvenilir İşleme (Reliability):** Mesajlar ancak AI başarısıyla kaydedildiğinde "işlendi" olarak işaretlenir. API hatalarında veri kaybı önlenir.

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

## Hafıza Kuralları ve Protokolü

Bu proje, aşağıdaki merkezi protokole tam bağlılıkla (Strict Compliance) yönetilmektedir:

> [!IMPORTANT]
> **Küresel Protokol:** [GLOBAL_MEMORY_PROTOCOL_v1.md](file:///C:/Users/YUSUF%20%C3%87%C4%B0NAR/.gemini/antigravity/GLOBAL_MEMORY_PROTOCOL_v1.md)

### Yerel Uygulama Detayları:
1.  **İzolasyon:** Hafıza verisi sadece bu dizindeki `memory/` klasöründe saklanır.
2.  **Şema:** [schema.json](file:///c:/Users/YUSUF%20%C3%87%C4%B0NAR/OneDrive/Belgeler/Masa%C3%BCst%C3%BC/projelerim/maviLojistik/memory/schema.json) (v1.1) tüm kayıtlarda zorunludur.
3.  **Audit:** `task_history.md` dosyası her `DONE` görevinde küresel hash kuralına göre güncellenir.
