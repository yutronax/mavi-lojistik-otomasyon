# -*- coding: utf-8 -*-
"""
Quality Gate Agent - Ayrıştırma Sonuçlarını Denetleyen Gözlemci Ajan
Purpose:      Gemini çıktılarını orijinal mesajla karşılaştırıp doğruluk puanı verir.
Inputs:       original_message (str), parsed_json (dict)
Outputs:      confidence_score (float), issues (list)
Dependencies: src.utils.gemini_adapter
Usage:        OrchestratorSDK tarafından her parse işleminden sonra çağrılır.
"""

import json
import os
import logging
from typing import Dict, Any, Tuple, List
from openai import OpenAI

logger = logging.getLogger(__name__)

class QualityGate:
    SYSTEM_PROMPT = """Sen bir LOJİSTİK VERİ DENETÇİSİSİN. 
Görevin: Bir WhatsApp mesajı ile bu mesajdan çıkartılmış JSON verisini karşılaştırıp DOĞRULUK PUANI vermek.

DENETİM KRİTERLERİ:
1. KONUM DOĞRULUĞU: Mesajda geçen şehir/ilçeler JSON'da doğru eşleşmiş mi? (Örn: Mesajda "İzmir" varken JSON'da "İstanbul" varsa puan kır.)
2. TELEFON: Mesajdaki telefon numarası JSON'da eksiksiz var mı?
3. HALLÜSİNASYON: Mesajda OLMAYAN bir bilgi JSON'a eklenmiş mi?
4. EKSİK VERİ: Mesajda net olan bir bilgi (fiyat, tonaj) JSON'da atlanmış mı?

PUANLAMA:
0.0 ile 1.0 arasında bir sayı ver. 
- 0.95+: Kusursuz.
- 0.80 - 0.94: Küçük eksikler var ama güvenilir.
- 0.50 - 0.79: Şüpheli, kontrol edilmeli.
- 0.49 ve altı: Kesinlikle hatalı veya uydurma.

SADECE AŞAĞIDAKİ FORMATTA JSON DÖNDÜR:
{
  "score": 0.95,
  "issues": ["küçük bir hata açıklaması veya boş liste"],
  "is_reliable": true
}
"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.model = 'deepseek-chat'
        self.base_url = os.getenv('LLM_BASE_URL', 'https://api.deepseek.com/v1')
        self.enabled = os.getenv('ENABLE_QUALITY_GATE', '1').lower() in ('1', 'true', 'yes')

    def evaluate(self, original_message: str, parsed_data: List[Dict[str, Any]]) -> Tuple[float, List[str]]:
        """
        Ayrıştırılan veriyi orijinal mesajla karşılaştırır.
        """
        if not self.enabled:
            return 1.0, []

        try:
                        
            # Denetim için prompt hazırla
            check_payload = {
                "original": original_message,
                "parsed": parsed_data
            }
            
            prompt = f"{self.SYSTEM_PROMPT}\n\nVERİ:\n{json.dumps(check_payload, ensure_ascii=False)}"
            
            # DeepSeek API ile değerlendirme
            client = OpenAI(base_url=self.base_url, api_key=self.api_key, max_retries=0)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                timeout=20
            )
            response_text = response.choices[0].message.content

            if not response_text:
                return 0.5, ["Gözlemci ajan yanıt vermedi."]

            clean_json = response_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(clean_json)
            
            score = float(result.get('score', 0.5))
            issues = result.get('issues', [])
            
            logger.info(f"[QUALITY] Score: {score} | Issues: {len(issues)}")
            return score, issues

        except Exception as e:
            logger.error(f"QualityGate Error: {e}")
            return 0.6, [f"Denetim hatası: {str(e)}"]

    def is_safe_to_submit(self, score: float, threshold: float = 0.5) -> bool:
        """Güven puanı eşiğin üzerindeyse True döner."""
        return score >= threshold
