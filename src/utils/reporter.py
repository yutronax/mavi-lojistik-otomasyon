# -*- coding: utf-8 -*-
"""
reporter.py

Sistem durumu, 3 saatlik özetler ve kritik hata bildirimlerini WhatsApp üzerinden gönderir.
"""
import requests
import json
import logging
from datetime import datetime, timedelta
from src.utils.config import WHATSAPP_TOKEN, REPORT_PHONE, WHATSAPP_API_BASE_URL

logger = logging.getLogger(__name__)

class Reporter:
    def __init__(self):
        self.token = WHATSAPP_TOKEN
        self.target_phone = REPORT_PHONE
        self.base_url = WHATSAPP_API_BASE_URL
        
        # Oturum istatistikleri
        self.stats = {
            "start_time": datetime.now(),
            "messages_fetched": 0,
            "parsed_successfully": 0,
            "auto_approved": 0,
            "errors": []
        }

    def reset_stats(self):
        """İstatistikleri sıfırla (Genellikle rapor sonrası çağrılır)"""
        self.stats = {
            "start_time": datetime.now(),
            "messages_fetched": 0,
            "parsed_successfully": 0,
            "auto_approved": 0,
            "errors": []
        }

    def add_error(self, error_msg, is_critical=False):
        """Hata kaydet ve eğer kritikse anında bildir"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_error = f"[{timestamp}] {'[CRITICAL]: ' if is_critical else '[WARN] '} {error_msg}"
        self.stats["errors"].append(formatted_error)
        
        if is_critical:
            self.send_critical_alert(error_msg)

    def log_activity(self, fetched=0, parsed=0, approved=0):
        """Aktivite sayılarını güncelle"""
        self.stats["messages_fetched"] += fetched
        self.stats["parsed_successfully"] += parsed
        self.stats["auto_approved"] += approved

    def send_whatsapp_message(self, text):
        """Whapi üzerinden mesaj gönder"""
        if not self.token or not self.target_phone:
            logger.warning("WhatsApp bildirimleri için TOKEN veya TELEFON eksik.")
            return False

        url = f"{self.base_url}/messages/text"
        
        # Telefon numarasını temizle ve formatla (90XXXXXXXXXX)
        clean_phone = "".join(filter(str.isdigit, str(self.target_phone)))
        if len(clean_phone) == 10:
            clean_phone = "90" + clean_phone
        elif clean_phone.startswith("0") and len(clean_phone) == 11:
            clean_phone = "90" + clean_phone[1:]
        
        payload = {
            "to": f"{clean_phone}@s.whatsapp.net",
            "body": text
        }
        
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=20)
            if response.status_code in [200, 201]:
                logger.info(f"[OK] WhatsApp bildirimi gönderildi: {clean_phone}")
                return True
            else:
                logger.error(f"[ERR] WhatsApp gönderim hatası ({response.status_code}): {response.text}")
                return False
        except Exception as e:
            logger.error(f"[ERR] WhatsApp bildirim hatası: {e}")
            return False

    def send_critical_alert(self, error_msg):
        """Kritik hata anlık bildirimi"""
        alert_text = (
            "[ALERT] *KRİTİK SİSTEM HATASI* [ALERT]\n"
            "--------------------\n"
            f"[DATE] *Tarih:* {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"[FAIL] *HATA:* {error_msg}\n\n"
            "[WARN] Lütfen sunucuyu kontrol edin!"
        )
        return self.send_whatsapp_message(alert_text)

    def send_3hour_summary(self):
        """3 Saatlik özet raporu gönder"""
        now = datetime.now()
        duration = now - self.stats["start_time"]
        
        # Hata listesini hazırla (Öncelikli)
        error_section = ""
        if self.stats["errors"]:
            # Son 10 hatayı al
            recent_errors = self.stats["errors"][-10:]
            error_section = "[ERROR] *HATALAR (Öncelikli)*\n" + "\n".join(recent_errors) + "\n\n"
        else:
            error_section = "[OK] *Son 3 saatte kritik hata oluşmadı.*\n\n"

        summary_text = (
            "[SUMMARY] *3 SAATLİK SİSTEM ÖZETİ* [SUMMARY]\n"
            "--------------------\n"
            f"[TIME] *Dönem:* {self.stats['start_time'].strftime('%H:%M')} - {now.strftime('%H:%M')}\n"
            f"[STATS] *Süre:* {int(duration.total_seconds() / 60)} dakika\n"
            "--------------------\n\n"
            f"{error_section}"
            "[STATS] *İSTATİSTİKLER:*\n"
            f"[IN] Toplam Çekilen: *{self.stats['messages_fetched']}*\n"
            f"🧠 Başarıyla Ayrıştırılan: *{self.stats['parsed_successfully']}*\n"
            f"[AUTO] Otomatik Onay/Gönderim: *{self.stats['auto_approved']}*\n"
        )
        
        # Risk Bilgisi Ekle (Opsiyonel)
        if hasattr(self, 'current_risk'):
            risk_labels = {3: "[OK] İYİ", 2: "[WARN] DİKKAT", 1: "[ERR] TEHLİKE"}
            label = risk_labels.get(self.current_risk, "Bilinmiyor")
            summary_text += f"[HEALTH] *WhatsApp Sağlığı:* {label}\n"

        summary_text += "\n🤖 _Mavi Lojistik Otonom Sunucu_"
        
        success = self.send_whatsapp_message(summary_text)
        if success:
            self.reset_stats() # Başarılıysa stats'ı sıfırla
        return success
