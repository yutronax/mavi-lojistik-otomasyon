#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Paralel Mahalle Verisi Oluşturucu

Gemini API kullanarak PARALEL olarak tüm il/ilçeler için mahalle listesi oluşturur.
5-10x daha hızlı!
"""

import os
import sys
import json
import time
from typing import List, Dict
import logging
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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

# Thread-safe counter
class Counter:
    def __init__(self):
        self.value = 0
        self.lock = threading.Lock()
    
    def increment(self):
        with self.lock:
            self.value += 1
            return self.value


class ParalelMahalleGenerator:
    """Paralel Gemini ile mahalle verisi oluşturucu"""
    
    AVAILABLE_MODELS = {
        '1': ('models/gemini-2.5-flash', 'Hızlı ve ekonomik (Önerilen)'),
        '2': ('models/gemini-2.5-pro', 'Daha detaylı ve doğru'),
        '3': ('models/gemini-3-flash-preview', 'En yeni deneysel model')
    }
    
    def __init__(self, il_ilceler_file: str, output_file: str, model_choice: str = '1', max_workers: int = 5):
        """
        Args:
            il_ilceler_file: il_ilçeler.json dosya yolu
            output_file: Çıktı dosyası
            model_choice: Model seçimi
            max_workers: Paralel thread sayısı (5-10 arası önerilen)
        """
        self.il_ilceler_file = il_ilceler_file
        self.output_file = output_file
        self.max_workers = max_workers
        
        # Model seçimi
        model_name, model_desc = self.AVAILABLE_MODELS.get(model_choice, self.AVAILABLE_MODELS['1'])
        logger.info(f"Secilen model: {model_name} - {model_desc}")
        logger.info(f"Paralel thread sayisi: {max_workers}")
        
        # Gemini model
        try:
            self.model = genai.GenerativeModel(model_name=model_name)
            logger.info(f"Model basariyla yuklendi: {model_name}")
        except Exception as e:
            logger.error(f"Model yuklenemedi: {e}")
            logger.info("Varsayilan model kullaniliyor: models/gemini-2.5-flash")
            self.model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        # Counters
        self.processed_counter = Counter()
        self.failed_ilceler = []
        self.failed_lock = threading.Lock()
        
        # Rate limiting (paralelde daha az bekleme)
        self.request_delay = 0.3  # 2s -> 0.3s (çok daha hızlı!)
        self.max_retries = 2  # 3 -> 2 (daha hızlı fail)
    
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
        """Gemini'ye belirli bir ilçenin mahallelerini sor"""
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
                response = self.model.generate_content(prompt)
                
                if response and response.text:
                    mahalleler = self._parse_mahalle_response(response.text)
                    
                    if mahalleler:
                        return mahalleler
                
                time.sleep(self.request_delay)
                
            except Exception as e:
                error_msg = str(e)
                
                if attempt < self.max_retries - 1:
                    time.sleep(1)  # Kısa bekleme
                else:
                    with self.failed_lock:
                        self.failed_ilceler.append({'il': il, 'ilce': ilce, 'error': error_msg})
                    return []
        
        return []
    
    def _parse_mahalle_response(self, text: str) -> List[str]:
        """Gemini yanıtını parse et"""
        mahalleler = []
        
        for line in text.strip().split('\n'):
            line = line.strip()
            
            if not line:
                continue
            
            line = line.lstrip('0123456789.-*• ')
            
            if len(line) < 3 or len(line) > 50:
                continue
            
            if ':' in line or '(' in line:
                continue
            
            mahalleler.append(line)
        
        return mahalleler
    
    def process_single_ilce(self, il: str, ilce: str, total: int) -> Dict:
        """Tek bir ilçeyi işle (thread-safe)"""
        mahalleler = self.ask_gemini_for_mahalleler(il, ilce)
        
        processed = self.processed_counter.increment()
        
        if processed % 10 == 0:
            logger.info(f"ILERLEME: {processed}/{total} ilce tamamlandi")
        
        return {
            'ilce': ilce,
            'mahalleler': mahalleler
        }
    
    def generate_all_mahalleler_parallel(self, limit: int = None) -> List[Dict]:
        """
        Tüm il/ilçeler için PARALEL mahalle verisi oluştur
        
        Args:
            limit: Test için ilçe sayısı limiti
            
        Returns:
            İl/İlçe/Mahalle verisi
        """
        il_ilceler_data = self.load_il_ilceler()
        
        if not il_ilceler_data:
            logger.error("Il/ilce verisi yuklenemedi!")
            return []
        
        # Tüm ilçeleri düz liste haline getir
        all_tasks = []
        for il_data in il_ilceler_data:
            il = il_data.get('il', '')
            ilceler = il_data.get('ilçe', [])
            
            for ilce in ilceler:
                all_tasks.append((il, ilce))
                if limit and len(all_tasks) >= limit:
                    break
            
            if limit and len(all_tasks) >= limit:
                break
        
        total_ilceler = len(all_tasks)
        logger.info(f"Toplam {total_ilceler} ilce PARALEL olarak islenecek")
        logger.info(f"Thread sayisi: {self.max_workers}")
        
        # Paralel işlem
        result_dict = {}  # {il: [ilce_data, ...]}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.process_single_ilce, il, ilce, total_ilceler): (il, ilce)
                for il, ilce in all_tasks
            }
            
            # Collect results
            for future in as_completed(future_to_task):
                il, ilce = future_to_task[future]
                
                try:
                    ilce_data = future.result()
                    
                    if il not in result_dict:
                        result_dict[il] = []
                    
                    result_dict[il].append(ilce_data)
                    
                except Exception as e:
                    logger.error(f"Hata: {il}/{ilce} - {e}")
        
        # Convert dict to list format
        result = []
        for il, ilceler in result_dict.items():
            result.append({
                'il': il,
                'ilceler': ilceler
            })
        
        logger.info(f"\nTAMAMLANDI: {total_ilceler} ilce islendi")
        
        return result
    
    def save_to_file(self, data: List[Dict]):
        """Veriyi dosyaya kaydet"""
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"\n[OK] Veri kaydedildi: {self.output_file}")
            
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
    print("PARALEL MAHALLE VERISI OLUSTURUCU (Gemini AI)")
    print("5-10x DAHA HIZLI!")
    print("="*60)
    
    # Dosya yolları
    data_dir = os.path.join(current_dir, 'data')
    il_ilceler_file = os.path.join(data_dir, 'il_ilçeler.json')
    output_file = os.path.join(data_dir, 'il_ilçe_mahalle.json')
    
    # Model seçimi
    print("\nMODEL SECIMI:")
    for key, (name, desc) in ParalelMahalleGenerator.AVAILABLE_MODELS.items():
        print(f"{key}. {name} - {desc}")
    
    model_choice = input("\nModel seciminiz (1/2/3) [1]: ").strip() or '1'
    
    # Thread sayısı
    print("\nPARALEL THREAD SAYISI:")
    print("3 - Yavas (guvenli)")
    print("5 - Orta (onerilen)")
    print("10 - Hizli (agresif)")
    
    workers_input = input("\nThread sayisi (3/5/10) [5]: ").strip() or '5'
    max_workers = int(workers_input)
    
    # Generator oluştur
    generator = ParalelMahalleGenerator(il_ilceler_file, output_file, model_choice, max_workers)
    
    # Kullanıcıya sor
    print("\nOPSIYONLAR:")
    print("1. TEST MODU (Ilk 10 ilce)")
    print("2. KISMI MOD (Ilk 100 ilce)")
    print("3. TAM MOD (Tum ilceler - ~971 ilce, ~10-20 dakika)")
    
    choice = input("\nSeciminiz (1/2/3): ").strip()
    
    limit = None
    if choice == '1':
        limit = 10
        print("\n[TEST MODU] Ilk 10 ilce PARALEL isleniyor...")
    elif choice == '2':
        limit = 100
        print("\n[KISMI MOD] Ilk 100 ilce PARALEL isleniyor...")
    else:
        print("\n[TAM MOD] TUM ilceler PARALEL isleniyor...")
        confirm = input("Emin misiniz? (E/H): ")
        if confirm.upper() != 'E':
            print("Iptal edildi.")
            return
    
    # Veri oluştur
    print("\nBaslatiliyor...\n")
    start_time = time.time()
    
    data = generator.generate_all_mahalleler_parallel(limit=limit)
    
    elapsed = time.time() - start_time
    
    # Kaydet
    if data:
        generator.save_to_file(data)
        
        # Başarısız ilçeler
        if generator.failed_ilceler:
            print(f"\n! UYARI: {len(generator.failed_ilceler)} ilce basarisiz oldu:")
            for failed in generator.failed_ilceler[:10]:
                print(f"  - {failed['il']}/{failed['ilce']}")
        
        print(f"\n[OK] BASARILI!")
        print(f"Toplam sure: {elapsed/60:.1f} dakika")
        print(f"Hiz: {len(data)/(elapsed/60):.1f} ilce/dakika")
    else:
        print("\n[ERROR] HATA: Veri olusturulamadi!")


if __name__ == "__main__":
    main()
