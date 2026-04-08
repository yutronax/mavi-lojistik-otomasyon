#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mahalle Verisi Oluşturucu

Gemini API kullanarak tüm il/ilçeler için mahalle listesi oluşturur.
"""

import os
import sys
import json
import time
from typing import List, Dict
import logging
import io

# UTF-8 encoding zorlaması (Windows için)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Proje kök dizinini ekle
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'src'))

# Gemini import
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()
    
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not GEMINI_API_KEY:
        print("HATA: GEMINI_API_KEY bulunamadi!")
        sys.exit(1)
    
    genai.configure(api_key=GEMINI_API_KEY, transport='rest')
    GEMINI_AVAILABLE = True
except Exception as e:
    print(f"HATA: Gemini yuklenemedi: {e}")
    GEMINI_AVAILABLE = False
    sys.exit(1)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MahalleDataGenerator:
    """Gemini ile mahalle verisi oluşturucu"""
    
    # Kullanılabilir modeller
    AVAILABLE_MODELS = {
        '1': ('models/gemini-2.5-flash', 'Hızlı ve ekonomik (Önerilen)'),
        '2': ('models/gemini-2.5-pro', 'Daha detaylı ve doğru'),
        '3': ('models/gemini-3-flash-preview', 'En yeni deneysel model')
    }
    
    def __init__(self, il_ilceler_file: str, output_file: str, model_choice: str = '1'):
        """
        Args:
            il_ilceler_file: il_ilçeler.json dosya yolu
            output_file: Çıktı dosyası (il_ilçe_mahalle.json)
            model_choice: Model seçimi ('1', '2', veya '3')
        """
        self.il_ilceler_file = il_ilceler_file
        self.output_file = output_file
        
        # Model seçimi
        model_name, model_desc = self.AVAILABLE_MODELS.get(model_choice, self.AVAILABLE_MODELS['1'])
        logger.info(f"Secilen model: {model_name} - {model_desc}")
        
        # Gemini model (safety settings olmadan)
        try:
            self.model = genai.GenerativeModel(model_name=model_name)
            logger.info(f"Model basariyla yuklendi: {model_name}")
        except Exception as e:
            logger.error(f"Model yuklenemedi: {e}")
            logger.info("Varsayilan model kullaniliyor: models/gemini-2.5-flash")
            self.model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        # Rate limiting
        self.request_delay = 2  # Saniye (API limitleri için)
        self.requests_made = 0
        self.max_retries = 3
        self.failed_ilceler = []  # Başarısız ilçeleri takip et
        
    def load_il_ilceler(self) -> List[Dict]:
        """il_ilçeler.json dosyasını yükle"""
        try:
            with open(self.il_ilceler_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"{len(data)} il yuklendi")
            return data
        except Exception as e:
            logger.error(f"Dosya yuklenemedi: {e}")
            return []
    
    def ask_gemini_for_mahalleler(self, il: str, ilce: str) -> List[str]:
        """
        Gemini'ye belirli bir ilçenin mahallelerini sor
        
        Args:
            il: İl adı
            ilce: İlçe adı
            
        Returns:
            Mahalle listesi
        """
        prompt = f"""
Türkiye'de {il} ili, {ilce} ilçesinin en bilinen ve önemli mahallelerini listele.

KURALLAR:
1. Sadece gerçek, resmi mahalle adlarını ver
2. En az 5, en fazla 15 mahalle listele
3. Merkez mahalleleri ve önemli semtleri dahil et
4. Her satırda bir mahalle adı olsun
5. Numaralandırma, tire veya başka işaret kullanma
6. Sadece mahalle adlarını ver, açıklama yapma

Örnek format:
Bahçelievler
Cumhuriyet
Merkez
Yenimahalle
"""
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"  Gemini'ye sorgulanıyor: {il}/{ilce} (Deneme {attempt + 1})")
                
                response = self.model.generate_content(prompt)
                self.requests_made += 1
                
                # Yanıtı parse et
                if response and response.text:
                    mahalleler = self._parse_mahalle_response(response.text)
                    
                    if mahalleler:
                        logger.info(f"  ✓ {len(mahalleler)} mahalle bulundu")
                        return mahalleler
                    else:
                        logger.warning(f"  ! Mahalle listesi bos")
                
                # Rate limiting
                time.sleep(self.request_delay)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"  X Hata (Deneme {attempt + 1}): {error_msg}")
                
                # Blocked content kontrolü
                if 'block' in error_msg.lower() or 'safety' in error_msg.lower():
                    logger.warning(f"  ! Icerik guvenlik filtresine takildi, baska prompt deneniyor...")
                    # Alternatif prompt dene
                    if attempt < self.max_retries - 1:
                        time.sleep(2)
                        continue
                
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    logger.info(f"  Bekleniyor: {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"  X {il}/{ilce} icin mahalle alinamadi!")
                    self.failed_ilceler.append({'il': il, 'ilce': ilce, 'error': error_msg})
                    return []
        
        return []
    
    def _parse_mahalle_response(self, text: str) -> List[str]:
        """Gemini yanıtını parse et"""
        mahalleler = []
        
        for line in text.strip().split('\n'):
            line = line.strip()
            
            # Boş satırları atla
            if not line:
                continue
            
            # Numaralandırma, tire vb. temizle
            line = line.lstrip('0123456789.-*• ')
            
            # Çok kısa veya çok uzun olanları atla
            if len(line) < 3 or len(line) > 50:
                continue
            
            # Açıklama içerenleri atla
            if ':' in line or '(' in line:
                continue
            
            mahalleler.append(line)
        
        return mahalleler
    
    def generate_all_mahalleler(self, limit: int = None) -> Dict:
        """
        Tüm il/ilçeler için mahalle verisi oluştur
        
        Args:
            limit: Test için ilçe sayısı limiti (None = tümü)
            
        Returns:
            İl/İlçe/Mahalle verisi
        """
        il_ilceler_data = self.load_il_ilceler()
        
        if not il_ilceler_data:
            logger.error("Il/ilce verisi yuklenemedi!")
            return {}
        
        result = []
        total_ilceler = sum(len(item.get('ilçe', [])) for item in il_ilceler_data)
        processed = 0
        
        logger.info(f"Toplam {total_ilceler} ilce icin mahalle verisi olusturulacak")
        
        if limit:
            logger.info(f"TEST MODU: Sadece ilk {limit} ilce isleniyor")
        
        for il_data in il_ilceler_data:
            il = il_data.get('il', '')
            ilceler = il_data.get('ilçe', [])
            
            logger.info(f"\n{'='*60}")
            logger.info(f"IL: {il} ({len(ilceler)} ilce)")
            logger.info(f"{'='*60}")
            
            il_result = {
                'il': il,
                'ilceler': []
            }
            
            for ilce in ilceler:
                processed += 1
                
                # Limit kontrolü
                if limit and processed > limit:
                    logger.info(f"\nLIMIT ASILDI: {limit} ilce islendi")
                    result.append(il_result)
                    return result
                
                logger.info(f"[{processed}/{total_ilceler}] {il} / {ilce}")
                
                # Gemini'ye sor
                mahalleler = self.ask_gemini_for_mahalleler(il, ilce)
                
                ilce_data = {
                    'ilce': ilce,
                    'mahalleler': mahalleler
                }
                
                il_result['ilceler'].append(ilce_data)
                
                # Progress
                if processed % 10 == 0:
                    logger.info(f"\nILERLEME: {processed}/{total_ilceler} ilce tamamlandi")
                    logger.info(f"Toplam API istegi: {self.requests_made}")
            
            result.append(il_result)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"TAMAMLANDI: {processed} ilce islendi")
        logger.info(f"Toplam API istegi: {self.requests_made}")
        logger.info(f"{'='*60}")
        
        return result
    
    def save_to_file(self, data: Dict):
        """Veriyi dosyaya kaydet"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"\n✓ Veri kaydedildi: {self.output_file}")
            
            # İstatistikler
            total_iller = len(data)
            total_ilceler = sum(len(il.get('ilceler', [])) for il in data)
            total_mahalleler = sum(
                len(ilce.get('mahalleler', []))
                for il in data
                for ilce in il.get('ilceler', [])
            )
            
            logger.info(f"\nISTATISTIKLER:")
            logger.info(f"  - Iller: {total_iller}")
            logger.info(f"  - Ilceler: {total_ilceler}")
            logger.info(f"  - Mahalleler: {total_mahalleler}")
            
        except Exception as e:
            logger.error(f"Dosya kaydedilemedi: {e}")


def main():
    """Ana fonksiyon"""
    print("\n" + "="*60)
    print("MAHALLE VERISI OLUSTURUCU (Gemini AI)")
    print("="*60)
    
    # Dosya yolları
    data_dir = os.path.join(current_dir, 'data')
    il_ilceler_file = os.path.join(data_dir, 'il_ilçeler.json')
    output_file = os.path.join(data_dir, 'il_ilçe_mahalle.json')
    
    # Model seçimi
    print("\nMODEL SECIMI:")
    for key, (name, desc) in MahalleDataGenerator.AVAILABLE_MODELS.items():
        print(f"{key}. {name} - {desc}")
    
    model_choice = input("\nModel seciminiz (1/2/3) [1]: ").strip() or '1'
    
    # Generator oluştur
    generator = MahalleDataGenerator(il_ilceler_file, output_file, model_choice)
    
    # Kullanıcıya sor
    print("\nOPSIYONLAR:")
    print("1. TEST MODU (Ilk 5 ilce)")
    print("2. KISMI MOD (Ilk 50 ilce)")
    print("3. TAM MOD (Tum ilceler - ~900 ilce, ~30-60 dakika)")
    
    choice = input("\nSeciminiz (1/2/3): ").strip()
    
    limit = None
    if choice == '1':
        limit = 5
        print("\n[TEST MODU] Ilk 5 ilce isleniyor...")
    elif choice == '2':
        limit = 50
        print("\n[KISMI MOD] Ilk 50 ilce isleniyor...")
    else:
        print("\n[TAM MOD] TUM ilceler isleniyor...")
        confirm = input("Emin misiniz? Bu 30-60 dakika surebilir (E/H): ")
        if confirm.upper() != 'E':
            print("Iptal edildi.")
            return
    
    # Veri oluştur
    print("\nBaslatiliyor...\n")
    data = generator.generate_all_mahalleler(limit=limit)
    
    # Kaydet
    if data:
        generator.save_to_file(data)
        
        # Başarısız ilçeler varsa göster
        if generator.failed_ilceler:
            print(f"\n! UYARI: {len(generator.failed_ilceler)} ilce basarisiz oldu:")
            for failed in generator.failed_ilceler[:10]:  # İlk 10'unu göster
                print(f"  - {failed['il']}/{failed['ilce']}: {failed['error'][:50]}...")
            
            if len(generator.failed_ilceler) > 10:
                print(f"  ... ve {len(generator.failed_ilceler) - 10} tane daha")
        
        print("\n[OK] BASARILI!")
    else:
        print("\n[ERROR] HATA: Veri olusturulamadi!")


if __name__ == "__main__":
    main()
