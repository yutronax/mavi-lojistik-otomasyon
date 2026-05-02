# Mavi Lojistik Otomasyon Sistemi

## Proje Amacı
WhatsApp gruplarından gelen lojistik yük ilanlarını otomatik olarak çeken, yapay zeka (Google Gemini) ile ayrıştıran ve yapılandırılmış veri formatına dönüştüren bir masaüstü otomasyon uygulamasıdır. Onaylanan ilanları YukBurada.com gibi dış sistemlere aktarır.

## Teknoloji Yığını
- **Dil**: Python 3.10+
- **Arayüz**: Flet (Flutter tabanlı Python framework)
- **Yapay Zeka**: Google Gemini API
- **WhatsApp Entegrasyonu**: Whapi.cloud
- **Veri Saklama**: JSON dosyaları (Atomik yazma prensibi ile)

## Klasör Yapısı
- `src/gui/`: Flet tabanlı kullanıcı arayüzü sayfaları ve bileşenleri.
- `src/fetchers/`: WhatsApp ve diğer veri kaynaklarından veri çekme modülleri.
- `src/parsers/`: Ham mesajları işleyen ve AI ile ayrıştıran mantık.
- `src/services/`: Veri yönetimi ve dosya işlemleri servisleri.
- `src/utils/`: Doğrulama, eşleştirme ve sunucu yönetimi gibi yardımcı araçlar.
- `data/`: Şehir/ilçe listeleri, yük tipleri gibi statik veri dosyaları.
- `memory/`: Projenin geçmişini ve yapısını tutan bellek dosyaları.

## Kritik Dosyalar
- `src/gui/flet_app.py`: Uygulamanın ana giriş noktası (Flet).
- `src/gui/pages/management_center.py`: Yönetim Merkezi sayfası (Yük kuralları, gruplar vb.).
- `src/gui/pages/operation_center.py`: Operasyon Merkezi (İlanların listelendiği ana sayfa).
- `text_gen_parser.py`: Gemini entegrasyonlu ana ayrıştırma motoru.
- `vps_main.py`: VPS üzerinde çalışan arka plan servisinin ana dosyası.
