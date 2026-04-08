# 🚚 Uygulama Taşıma ve Kurulum Rehberi

Uygulamayı başka bir bilgisayarda çalıştırmak için aşağıdaki adımları takip edebilirsiniz.

## 1. Hazır Sürümü Kullanma (Önerilen)

En kolay yöntem, hali hazırda oluşturulmuş olan `.exe` sürümünü kopyalamaktır.

1.  Proje ana dizinindeki **`build.bat`** dosyasını çift tıklayıp çalıştırın. (Bu işlem biraz sürebilir, "Build completed!" yazısını bekleyin).
2.  İşlem bittikten sonra proje klasöründe **`dist`** adında bir klasör oluşacak (veya güncellenecektir).
3.  **`dist/MaviLojistik`** klasörünün tamamını USB belleğe veya diğer bilgisayara kopyalayın.
    *   *Not: Bu klasör sadece çalıştırılabilir dosyaları içerir, kaynak kodlarınızı (py dosyalarını) içermez.*
3.  **`dist/MaviLojistik`** klasörünün tamamını USB belleğe veya diğer bilgisayara kopyalayın.
    *   *Not: Bu klasör sadece çalıştırılabilir dosyaları içerir, kaynak kodlarınızı (py dosyalarını) içermez.*
4.  **Kontrol:** `dist/MaviLojistik` klasörü içinde **`.env`** dosyasının olduğundan emin olun. (`build.bat` bunu otomatik kopyalar, ancak yine de kontrol etmekte fayda var).

**Diğer Bilgisayarda:**
*   `MaviLojistik` klasörünü masaüstüne (veya istediğiniz yere) yapıştırın.
*   Klasör içindeki **`MaviLojistik.exe`** dosyasına çift tıklayarak çalıştırın.

---

## 2. Kaynak Koddan Çalıştırma (Geliştiriciler İçin)

Eğer kaynak kodları taşımak istiyorsanız:

1.  Python 3.10+ yüklü olduğundan emin olun.
2.  Proje klasörünü kopyalayın (`.venv`, `__pycache__`, `dist`, `build` klasörlerini hariç tutabilirsiniz).
3.  Terminal/Komut İstemi'ni açın ve proje klasörüne gidin.
4.  Gerekli kütüphaneleri yükleyin:
    ```cmd
    pip install -r requirements.txt
    ```
5.  Uygulamayı başlatın:
    ```cmd
    python src/gui/masaustu_uygulama.py
    ```

## Notlar
*   Uygulama internet bağlantısı gerektirir.
*   `.env` dosyasının eksik olması durumunda WhatsApp entegrasyonu çalışmayabilir.
