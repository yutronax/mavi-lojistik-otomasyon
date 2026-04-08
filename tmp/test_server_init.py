# -*- coding: utf-8 -*-
"""
test_server_init.py

Sanal sunucu motorunun (ServerWorker) ve Raporlayıcının (Reporter) 
başlatma (init) ve iç aktarma (import) kontrollerini gerçekleştirir.
"""
import sys
import os

# Proje kök dizinini sys.path'e ekle
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def test_imports():
    print("--- Modül Aktarma Testi ---")
    try:
        from src.utils.reporter import Reporter
        from server_worker import ServerWorker
        print("✅ reporter.py ve server_worker.py başarıyla aktarıldı.")
        return True
    except ImportError as e:
        print(f"❌ Aktarma Hatası: {e}")
        return False

def test_initialization():
    print("\n--- Başlatma (Init) Testi ---")
    try:
        from src.utils.reporter import Reporter
        from server_worker import ServerWorker
        
        reporter = Reporter()
        print("✅ Reporter nesnesi oluşturuldu.")
        
        # Test mesajı göndermeyi DENEMEYECEĞİZ (sahte token durumunda hata verir)
        
        worker = ServerWorker()
        print("✅ ServerWorker nesnesi oluşturuldu.")
        print(f"   Çalışma Saatleri: {worker.start_hour:02d}:00 - {worker.end_hour:02d}:00")
        
        return True
    except Exception as e:
        print(f"❌ Başlatma Hatası: {e}")
        return False

if __name__ == "__main__":
    s1 = test_imports()
    s2 = test_initialization()
    
    if s1 and s2:
        print("\n✅ TÜM SUNUCU BİLEŞENLERİ KULLANIMA HAZIR!")
        sys.exit(0)
    else:
        print("\n❌ SUNUCU BİLEŞENLERİNDE HATA VAR!")
        sys.exit(1)
