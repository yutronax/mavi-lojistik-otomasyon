
# -*- coding: utf-8 -*-
import sys
import os
import logging

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('RunFullOnce')

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir) # tools -> root (maviLojistik)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Load env
from dotenv import load_dotenv
load_dotenv()

from src.utils.config import FETCH_HOURS_BACK
from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

def main():
    logger.info("🚀 MANUEL TETİKLEME BAŞLATILIYOR...")
    logger.info(f"📂 Proje Kök Dizini: {project_root}")
    
    try:
        # Initialize Orchestrator
        orchestrator = OrchestratorSDK()
        
        # 1. Fetch new messages (This puts them in queue)
        # Using a slightly larger window just for this run to be safe
        logger.info("🌐 Mesajlar çekiliyor (Son 24 saat)...")
        # Override config for this run via env var if needed, but fetch_all_messages defaults to config
        
        # Manually trigger the fetch logic
        from src.fetchers.whapi_fetcher import fetch_all_messages
        count = fetch_all_messages(hours_back=24, only_saved_groups=True)
        # count = fetch_all_messages(hours_back=24, only_saved_groups=True, orchestrator=None)  # orchestrator argumanini kaldirdim veya None yaptim
        logger.info(f"📥 {count} yeni mesaj kuyruğa eklendi/güncellendi.")
        
        # 2. Process pending queue
        logger.info("⚙️ Kuyruk işleniyor...")
        # Orchestrator's run_once method processes the queue
        orchestrator.run_once(keep_only_today=False) 
        
        logger.info("✅ İŞLEM TAMAMLANDI.")
        
    except Exception as e:
        logger.error(f"❌ HATA: {e}", exc_info=True)

if __name__ == "__main__":
    main()
