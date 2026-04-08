# -*- coding: utf-8 -*-
"""
vps_main.py

Mavi Lojistik Otonom Sunucu Motoru (Headless Mode)
Bu dosya PM2 tarafından 24/7 çalıştırılmak üzere tasarlanmıştır.
"""

import os
import sys
import time
import logging
import traceback
from datetime import datetime

# Proje Kök Dizini Ayarı
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Reporter ve Orkestratör Importları
from src.utils.reporter import Reporter
from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

# Logging Yapılandırması
LOG_DIR = os.path.join(PROJECT_ROOT, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)
vps_log = os.path.join(LOG_DIR, 'vps_runtime.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(vps_log, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('VPS_Engine')

def is_working_hours():
    """
    Sistemin çalışma saatlerini kontrol eder (07:00 - 24:00).
    """
    now = datetime.now()
    # 07:00 ile 23:59:59 arası (24:00 dahil değil, 00:00'da biter)
    working = 7 <= now.hour <= 23
    return working

def run_vps_service():
    """
    Sistemi otonom döngüde çalıştırır.
    Hata durumunda WhatsApp üzerinden bildirim gönderir.
    """
    reporter = Reporter()
    
    logger.info("🚀 Mavi Lojistik Otonom Servis Başlatılıyor...")
    
    # Başlangıç bildirimi (Opsiyonel)
    try:
        reporter.add_error("🚀 *Sistem Başlatıldı*\nVPS üzerinde otonom döngü aktif.", level="INFO")
    except:
        pass

    while True:
        try:
            if not is_working_hours():
                now_str = datetime.now().strftime('%H:%M')
                logger.info(f"😴 Mesai dışı saat ({now_str}). Sistem uyku modunda. Sabit 07:00'ye kadar bekleniyor...")
                # 10 dakika bekle ve tekrar kontrol et
                time.sleep(600)
                continue

            # Orkestratörü başlat
            orchestrator = OrchestratorSDK()
            
            logger.info("🟢 Çalışma saatleri içinde. Orkestratör döngüsü başlatılıyor...")
            # Ana döngüyü çalıştır (Bu fonksiyon sonsuz döngü içerir)
            orchestrator.run_loop()
            
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"❌ KRİTİK HATA: {e}\n{error_details}")
            
            # WhatsApp üzerinden bildirim gönder
            try:
                reporter.add_error(
                    f"⚠️ *Kritik Sistem Hatası*\n\n"
                    f"Hata: {str(e)}\n"
                    f"Zaman: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                    f"Sistem 60 saniye içinde kendini yeniden başlatacak.",
                    level="CRITICAL"
                )
            except Exception as re:
                logger.error(f"Rapor gönderilemedi: {re}")
            
            # PM2 zaten otomatik yeniden başlatır ama biz de kısa bir mola verelim
            time.sleep(60)

if __name__ == "__main__":
    run_vps_service()
