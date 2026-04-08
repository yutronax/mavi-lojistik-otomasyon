# Mavi Lojistik VPS Kurulum Rehberi

Bu döküman, sistemin bir Linux VPS (Ubuntu/Debian önerilir) üzerinde nasıl kurulacağını ve çalıştırılacağını anlatır.

> [!IMPORTANT]
> **Çalışma Saatleri:** Sistem her gün **07:00 - 00:00 (24:00)** saatleri arasında aktiftir. Gece yarısından sabah 07:00'ye kadar otomatik olarak uyku moduna geçer.
> **IP Adresi:** Webhook sunucusu `10.114.0.2` IP'sine bağlanacak şekilde yapılandırılmıştır.

## 1. Sistemin Güncellenmesi ve Gerekli Paketlerin Kurulması

Terminali açın ve şu komutları sırasıyla çalıştırın:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git nodejs npm
```

## 2. PM2 Kurulumu (Süreci Yönetmek İçin)

Sistemin kapanması durumunda otomatik yeniden başlaması için PM2 gereklidir:

```bash
sudo npm install -g pm2
```

## 3. Projenin VPS'e Aktarılması

Eğer projeyi Git üzerinden yüklüyorsanız:

```bash
git clone <depo_urlniz>
cd mavi-lojistik-otomasyon
```

Veya dosyaları FTP/SCP ile manuel kopyaladıysanız, o klasöre gidin.

## 4. Python Sanal Ortam (Virtualenv) Kurulumu

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 5. Çevresel Değişkenlerin (.env) Hazırlanması

Yerel bilgisayarınızdaki `.env` dosyasını VPS'teki ana dizine kopyalayın. İçinde şu satırların olduğundan emin olun:

```env
WHATSAPP_REPORTER_NUMBER=905XXXXXXXXX  # Hata mesajlarının gideceği numara
GEMINI_API_KEY=your_api_key_here
WHAPI_TOKEN=your_whapi_token_here
```

## 6. Sistemin Başlatılması (PM2 ile)

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

## 7. Faydalı Komutlar

- **Logları İzlemek:** `pm2 logs mavi-lojistik-server`
- **Durumu Kontrol Etmek:** `pm2 status`
- **Anlık Logları İzlemek:** `tail -f logs/vps_runtime.log`
- **Sistemi Durdurmak:** `pm2 stop mavi-lojistik-server`
- **Sistemi Yeniden Başlatmak:** `pm2 restart mavi-lojistik-server`

---
> [!TIP]
> Logları izleyerek sistemin düzgün çalışıp çalışmadığını ve WhatsApp mesajlarının gönderilip gönderilmediğini kontrol edebilirsiniz.
