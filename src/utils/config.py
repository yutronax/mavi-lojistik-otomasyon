# -*- coding: utf-8 -*-
"""
config.py

Merkezi yapılandırma dosyası. Tüm zaman filtreleri ve bekleme süreleri buradan yönetilir.
"""
import os
import sys
from dotenv import load_dotenv

# .env dosyasını yükle
def load_config():
    """Environment değişkenlerini mutlak yol ile yükler (EXE uyumlu)"""
    if getattr(sys, 'frozen', False):
        # EXE modunda: EXE'nin yanındaki .env
        root = os.path.dirname(sys.executable)
    else:
        # Geliştirme modunda: src/utils'in 2 üstü
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    env_path = os.path.join(root, '.env')
    load_dotenv(env_path)

load_config()

# --- KIMLIK BILGILERI (AUTH) ---
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN') or os.getenv('WHAPI_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
REPORT_PHONE = os.getenv('WHATSAPP_REPORTER_NUMBER') or os.getenv('REPORT_PHONE', '5318407744') # Varsayılan rapor numarası
WHATSAPP_API_BASE_URL = "https://gate.whapi.cloud"
WHAPI_TOOLS_URL = "https://tools.whapi.cloud/services/riskOfBlocking"
AUTO_SUBMIT = os.getenv('AUTO_SUBMIT', 'true').lower() == 'true'

# --- ZAMAN FİLTRELERİ (SAAT CİNSİNDEN) ---

# WhatsApp'tan çekilecek mesajların geriye dönük süresi (Saat)
# fetch_all_messages(hours_back=...)
FETCH_HOURS_BACK = float(os.getenv('FETCH_HOURS_BACK', '12'))

# Kopya mesaj kontrolü penceresi (Saat)
# Aynı içeriğe sahip mesajlar bu süre içinde tekrar işlenmez (DataService.is_body_known)
DUPLICATE_CHECK_HOURS = float(os.getenv('DUPLICATE_CHECK_HOURS', '12.0'))

# --- DÖNGÜ VE BEKLEME SÜRELERİ (SANİYE CİNSİNDEN) ---

# WhatsApp API kontrol periyodu (Saniye) - fetch_all_messages sıklığı
WHATSAPP_POLL_INTERVAL = int(os.getenv('WHATSAPP_POLL_INTERVAL', '60'))

# Paketler (Batch) arası bekleme süresi (Saniye)
BATCH_SLEEP_TIME = float(os.getenv('BATCH_SLEEP_TIME', '15.0'))

# Tüm gruplar tarandıktan sonraki ana bekleme süresi (Saniye)
LOOP_WAIT_TIME = int(os.getenv('LOOP_WAIT_TIME', '150'))

# --- ARAYÜZ (GUI) AYARLARI (DAKİKA CİNSİNDEN) ---

# Başlangıçta uygulanan zaman filtresi (Dakika)
DEFAULT_UI_FILTER_MINUTES = os.getenv('DEFAULT_UI_FILTER_MINUTES', '60')

# Arayüzdeki zaman filtresi seçenekleri (Dakika)
UI_FILTER_OPTIONS = os.getenv('UI_FILTER_OPTIONS', '10,20,40,60,120,240,480,1440').split(',')
