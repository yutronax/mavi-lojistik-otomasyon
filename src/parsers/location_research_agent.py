# -*- coding: utf-8 -*-
"""
Location Research Agent - Yer İsimlerini Araştırıp Düzelten AI Agent

Bu agent mesajlardaki potansiyel yer isimlerini AI ile araştırır
ve yanlış yazılmış/kısaltılmış yerleri doğru tam adlarıyla değiştirir.

Örnek: "temeli" → "ankara sincan"
"""

import json
import re
import os
import sys
from typing import Optional, Dict, Any

# Proje kök dizinini ekle (standalone çalışırken)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.utils.gemini_adapter import generate_content_text

class LocationResearchAgent:
    """
    Yer isimlerini araştırıp düzelten AI agent (prefers Gemini SDK).

    # TODO (INSTRUCTIONS FOR AI / Vibe Code):
    # - This is a 'nice-to-have' enhancement (web lookup). Disable by default in production.
    # - Provide an explicit env toggle ENABLE_LOCATION_RESEARCH to turn it on for manual quality runs.
    # - Prefer cheaper default Gemini models (gemini-2.5-mini) when enabled.
    """

    SYSTEM_PROMPT = """Sen bir lojistik asistanısın. Görevin mesajlardaki ROTA BİLGİLERİNİ ZENGİNLEŞTİRMEK.

ANA KURAL:
Eğer mesajda "Şehir A - İlçe B" gibi bir rota varsa ve İlçe B, Şehir A'da değilse, İlçe B'nin GERÇEK şehrini ekle.

Örnekler:
- Girdi: "Ankara - Pendik yükü"
- Çıktı: "Ankara Merkez - İstanbul Pendik yükü" (Çünkü Pendik İstanbul'dadır)

- Girdi: "Bursa - Gebze tır lazım"
- Çıktı: "Bursa Merkez - Kocaeli Gebze tır lazım" (Çünkü Gebze Kocaeli'dedir)

- Girdi: "Adana - Ceyhan"
- Çıktı: "Adana - Adana Ceyhan" (Zaten aynı şehirdeyse veya belirsizse olduğu gibi bırak veya ilini ekle)

DİĞER KURALLAR:
1. Sadece yer isimlerini düzenle. Telefon, fiyat, yük tipi bilgilerine dokunma.
2. Yazım hatalarını düzelt (Istnbul -> İstanbul).
3. ASLA JSON DÖNDÜRME. SADECE DÜZELTİLMİŞ METNİ DÖNDÜR.
"""

    def __init__(self, api_key: Optional[str] = None):
        """Uses the adapter which is now backed by OllamaClient."""
        self.api_key = api_key
        try:
            from src.utils.gemini_adapter import generate_content_text
            self._adapter_available = True
        except Exception:
            self._adapter_available = False
            
        self.default_model = os.getenv('OLLAMA_MODEL', 'llama3.1')
        self.enabled = os.getenv('ENABLE_LOCATION_RESEARCH', '1').lower() in ('1','true','yes')
        if not self.enabled:
            print("[!] LocationResearchAgent disabled by default (set ENABLE_LOCATION_RESEARCH=1 to enable)")

    def research_and_correct_locations(self, message: str) -> str:
        """
        Mesajdaki yer isimlerini Ollama asistanı veya yapılandırılmış yapay zeka ile düzeltir.
        """
        if not self.enabled:
            print("[!] LocationResearchAgent disabled - skipping research for this message")
            return message

        if self._adapter_available:
            try:
                model = self.default_model
                full_prompt = f"{self.SYSTEM_PROMPT}\n\nMesajı düzelt: {message}"
                text = generate_content_text(self.api_key, model, full_prompt, response_mime_type='text/plain')
                
                corrected_message = text.strip() if text else message
                if corrected_message.startswith('{') or corrected_message.startswith('```'):
                    print(f"[!] LocationResearchAgent returned JSON/Code instead of text, ignoring: {corrected_message[:50]}...")
                    return message
                
                if not corrected_message:
                    return message
                return corrected_message
            except Exception as e:
                print(f"[!] Location research (Ollama/LLM) hatası: {e}")
                return message
        
        return message

    def process_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mesaj objesini işler, body'yi düzeltir.

        Args:
            msg: Mesaj dictionary'si

        Returns:
            Düzeltilmiş mesaj dictionary'si
        """
        if 'body' not in msg:
            return msg

        original_body = msg['body']
        corrected_body = self.research_and_correct_locations(original_body)

        # Eğer değiştiyse log yaz
        if corrected_body != original_body:
            print(f"[✓] Yer düzeltmesi: '{original_body}' → '{corrected_body}'")

        # Yeni mesaj objesi oluştur
        corrected_msg = msg.copy()
        corrected_msg['body'] = corrected_body
        corrected_msg['original_body'] = original_body  # Orijinali sakla

        return corrected_msg