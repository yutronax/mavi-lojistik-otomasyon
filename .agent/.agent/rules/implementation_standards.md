# Uygulama ve Doğrulama Standartları (Implementation & Verification Standards)

Bu belge, sistemde yapılan her türlü kod değişikliği ve yeni geliştirme için uyulması zorunlu kuralları tanımlar.

## 1. Fonksiyon Dokümantasyonu
Yapılan her fonksiyon değişikliğinde veya yeni fonksiyon eklenmesinde, fonksiyon adının hemen altına aşağıdaki bilgileri içeren detaylı bir açıklama eklenmelidir:
- **İşlev**: Fonksiyonun ne işe yaradığı.
- **Bağlantılar**: Nereye bağlı olduğu ve hangi bileşenlerle etkileşime girdiği.
- **Gereklilik**: Neden gerekli olduğu.
- **Kritik Kurallar**: Asla değişmemesi gereken noktalar ve kısıtlamalar.

## 2. Zorunlu Test ve Doğrulama
Bir değişiklik yapıldığında, bu değişiklik **test edilip doğrulanana kadar** kullanıcıya sunulamaz.
- Agent, değişikliklerin doğruluğundan emin olana kadar (test çıktıları, log incelemeleri veya simülasyonlar yoluyla) çalışmaya devam etmelidir.
- Kullanıcıya sunulan her çözüm "doğrulanmış" statüsünde olmalıdır.

## 3. Süreklilik
Bu kurallar `.agent/` klasöründe kalıcı olarak saklanmalı ve her işlemde referans alınmalıdır.
