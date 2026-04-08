# Teknik ve Ayrıntılı Proje Dokümantasyonu (Mavi Lojistik Otomasyonu)

## 1. Proje Özeti
Bu proje, WhatsApp gruplarından gelen lojistik yük ilanlarını otomatik olarak çeken, yapay zeka (Google Gemini) ile ayrıştıran ve yapılandırılmış veri formatına dönüştüren bir masaüstü otomasyon uygulamasıdır. Kullanıcı dostu bir arayüz ile gelen ilanları listeler, düzenleme imkanı sunar ve onaylanan ilanları dış sistemlere (örneğin YukBurada.com) aktarır.

## 2. Mimari Genel Bakış
Sistem, modüler bir yapıya sahiptir ve aşağıdaki temel katmanlardan oluşur:

1.  **Veri Toplama Katmanı (Fetchers)**: WhatsApp API (Whapi.cloud) üzerinden mesajları çeker.
2.  **Veri İşleme ve Ayrıştırma Katmanı (Parsers)**: Ham mesajları anlamlı lojistik verilerine (Nereden, Nereye, Araç Tipi vb.) dönüştürür.
3.  **Veri Yönetim Katmanı (Services)**: Verilerin saklanması, kara liste kontrolü, mükerrer veri engelleme ve dosya işlemlerini yönetir.
4.  **Kullanıcı Arayüzü (GUI)**: Tkinter tabanlı masaüstü uygulaması. Kullanıcının verileri görüntülemesini ve yönetmesini sağlar.

## 3. Bileşenler ve Detaylı Teknik Açıklamalar

### 3.1. Kullanıcı Arayüzü (`src/gui/masaustu_uygulama.py`)
Uygulamanın ana giriş noktasıdır. Tkinter kütüphanesi ile geliştirilmiştir.

*   **Ana Özellikler**:
    *   **Tablo Yapısı**: Onaylanmamış ve onaylanmış ilanlar sekmeli yapıda `ttk.Treeview` ile listelenir.
    *   **Canlı İzleme**: Arka planda çalışan worker thread'ler sayesinde yeni gelen mesajlar anlık olarak arayüze yansır.
    *   **Düzenleme Paneli**: Seçilen ilanın detayları sağ panelde düzenlenebilir (autocomplete özellikli giriş alanları).
    *   **Filtreleme**: Şehir, ilçe veya metin bazlı arama yapılabilir.
    *   **Grup ve Kara Liste Yönetimi**: WhatsApp grupları ve engellenecek numaralar GUI üzerinden yönetilebilir (`GroupManager`, `BlacklistManager` sınıfları).
    *   **Loglama**: İşlem geçmişi ve hatalar entegre log panelinde gösterilir.

### 3.2. Veri Çekme Modülü (`src/fetchers/whapi_fetcher.py`)
WhatsApp gruplarından mesajları çekmek için Whapi.cloud API'sini kullanır.

*   **Çalışma Mantığı**:
    *   `fetch_all_messages()` fonksiyonu belirli periyotlarla çalışır.
    *   **Pagination**: API'den iletiler sayfalama yapılarak çekilir (offset/limit).
    *   **Deduplication (Tekilleştirme)**: Aynı ID'ye sahip mesajlar tekrar kaydedilmez. Ayrıca içerik bazlı (`body`) hash kontrolü ile kısa süre içinde gelen aynı metinler ("spam") engellenir.
    *   **DNS Patch**: Bazı ağ kısıtlamalarını aşmak için `socket.getaddrinfo` yamalanarak statik IP kullanılır.
    *   **Filtreleme**: Sadece `data/chat_groups.json` dosyasında kayıtlı gruplardan veri çeker (Opsiyonel olarak tüm gruplar).

### 3.3. Ayrıştırma ve Yapay Zeka (`text_gen_parser.py`)
Projenin "beyni" olarak nitelendirilebilir. Gelen serbest metin formatındaki lojistik ilanlarını yapılandırılmış JSON verisine çevirir.

*   **Teknoloji**: Google Gemini (`gemini-3.1-pro-preview` modeli) kullanılır.
*   **Prompt Mühendisliği**: Model, 3 farklı ilan formatını (Yük İlanı, Satır Bazlı, Tek Cümle) tanıyacak şekilde eğitilmiştir.
*   **Doğrulama (Validation)**:
    *   **Halüsinasyon Koruması**: Modelin ürettiği şehir/ilçe bilgileri, `CityDistrictValidator` ile yerel veri tabanından (`il_ilçe_mahalle.json`) doğrulanır. Eğer metinde geçmeyen bir şehir üretildiyse (halüsinasyon), işlem iptal edilir veya düzeltilir.
    *   **Araç/Kasa Tipi Eşleştirme**: `VehicleTypeMatcher` sınıfı, metindeki anahtar kelimelere (`TIR`, `KIRKAYAK`, `LOWBED` vb.) göre standart tip tanımlarını yapar. Regex ve Levenshtein (bulanık eşleşme) algoritmaları kullanır.
    *   **Mahalle Çözümleme**: İlçe bilgisi eksikse, yapay zeka veya cache mekanizması ile mahalle isminden ilçe tespiti yapılır (`neighborhood_cache.json`).

### 3.4. Orkestrasyon (`src/parsers/veri_cekici_ayristirici.py`)
Veri çekme ve ayrıştırma süreçlerini koordine eder.

*   **Worker Thread**: `ThreadPoolExecutor` kullanarak mesajları arka planda paralel olarak işler.
*   **Kuyruk Yönetimi**: Çekilen mesajlar `processing_queue` kuyruğuna atılır ve sırayla işlenir.
*   **Dosya Yönetimi**: İşlenen veriler `onaylanmamis_ayristirilmis.json` dosyasına "atomic write" (güvenli yazma) prensibiyle kaydedilir.

### 3.5. Veri Servisi (`src/services/data_service.py`)
Tüm dosya okuma/yazma işlemleri için merkezi bir servis katmanıdır.

*   **Atomik Yazma**: `atomic_json_write` fonksiyonu ile veriler önce geçici dosyaya yazılır, başarılı olursa asıl dosyanın üzerine taşınır. Bu sayede elektrik kesintisi vb. durumlarda veri kaybı (corrupted file) önlenir.
*   **Yedekleme**: Her yazma işleminden önce otomatik `.bak` dosyası oluşturulur.
*   **Migration**: Uygulama ilk açıldığında gerekli veri dosyalarını (`juk_tipi.json`, `chat_groups.json`) kullanıcının veri dizinine kopyalar.

## 4. Veri Akış Şeması (Data Flow)

1.  **Fetch**: `WhapiFetcher` -> API'den mesajları çeker -> `mesajlar.json` ve Bellek Kuyruğu.
2.  **Filter**: `DataService.is_body_known()` -> Mükerrer içerikler ve Karaliste (`blacklist.json`) kontrolü yapılır.
3.  **Queue**: Geçerli mesajlar `Orchestrator` kuyruğuna eklenir.
4.  **Parse**:
    *   `TextGenParser` (Gemini) metni analiz eder.
    *   `Validator` çıktıları doğrular.
    *   `Matcher` araç tiplerini standartlaştırır.
5.  **Save**: Sonuçlar `onaylanmamis_ayristirilmis.json` dosyasına kaydedilir.
6.  **Display**: GUI (`masaustu_uygulama.py`), dosyayı okur ve ekrana basar.
7.  **Submission**: Kullanıcı "Onayla" dediğinde veri `onaylanan_kayitlar.json` dosyasına taşınır ve dış servise (`YukBuradaSubmitter`) gönderilir.

## 5. Dizin Yapısı ve Önemli Dosyalar

*   `src/gui/`: Arayüz kodları.
*   `src/fetchers/`: Veri çekme modülleri (Whapi).
*   `src/parsers/`: Ayrıştırma mantığı ve orkestrasyon.
*   `src/services/`: Veri yönetimi (DataService).
*   `src/utils/`: Yardımcı araçlar (Validator, Matcher, File Ops).
*   `data/`: Statik veri dosyaları (`il_ilceler.json`, `yuk_tipi.json`).
*   `text_gen_parser.py`: Gemini entegrasyonlu ana parser.

## 6. Kurulum ve Gereksinimler

*   **Python**: 3.10+
*   **Kütüphaneler**: `tkinter`, `requests`, `google-generativeai`, `pydantic`, `python-dotenv`.
*   **API Anahtarları**: `.env` dosyasında `GEMINI_API_KEY` ve `WHATSAPP_TOKEN` (veya `WHAPI_TOKEN`) tanımlı olmalıdır.

## 7. Gelecek Geliştirmeler (Roadmap)
*   Web tabanlı yönetim paneli (Next.js/React geçişi).
*   Çoklu kullanıcı desteği.
*   Daha fazla kaynak entegrasyonu (Telegram, Email vb.).
