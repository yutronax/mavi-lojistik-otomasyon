# -*- coding: utf-8 -*-
"""
Grup Senkronizasyon ve Filtreleme Betiği

Bu betik:
1. Whapi API'den güncel grupları çeker.
2. Mevcut 'data/chat_groups.json' içindeki grupları kontrol eder.
3. Numarada artık kayıtlı olmayanları (dead groups) listeden çıkarır.
4. Listeyi aktif gruplardan tam 100 adede tamamlar.
"""

import os
import sys
import json
import logging

# Proje kök dizinini sys.path'e ekle
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Gerekli modülleri içe aktar
try:
    from src.fetchers.whapi_fetcher import fetch_groups
    from src.utils.common import get_user_data_dir
    from src.utils.file_operations import save_json_safe, load_json_safe
except ImportError as e:
    print(f"Modül aktarma hatası: {e}")
    sys.exit(1)

# Logging yapılandırması
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def sync_groups_to_100():
    user_data_dir = get_user_data_dir()
    chat_groups_file = str(user_data_dir / 'chat_groups.json')
    
    # 1. Mevcut grupları yükle
    existing_groups = load_json_safe(chat_groups_file, default=[])
    if not isinstance(existing_groups, list):
        logger.error(f"Geçersiz grup dosyası formatı: {chat_groups_file}")
        return
    
    logger.info(f"Mevcut kayıtlı grup sayısı: {len(existing_groups)}")
    existing_ids = {str(g.get('id')): g for g in existing_groups if g.get('id')}
    
    # 2. API'den güncel grupları çek
    logger.info("Whapi API'den güncel gruplar çekiliyor...")
    api_groups = fetch_groups(max_count=500) # 500'e kadar çekelim ki seçeneğimiz olsun
    
    if not api_groups:
        logger.error("API'den hiç grup çekilemedi. İşlem iptal ediliyor.")
        return
    
    logger.info(f"API'den toplam {len(api_groups)} aktif grup alındı.")
    api_ids = {str(g.get('id')): g for g in api_groups if g.get('id')}
    
    # 3. Filtreleme: Mevcut olup hala API'de olanları koru
    valid_existing = []
    for gid, gdata in existing_ids.items():
        if gid in api_ids:
            valid_existing.append(gdata)
        else:
            logger.info(f"Kayıtlı olmayan grup çıkarıldı: {gdata.get('name')} ({gid})")
            
    logger.info(f"Hala geçerli olan eski grup sayısı: {len(valid_existing)}")
    
    # 4. Tamamlama veya Azaltma
    final_groups = []
    
    # Önce hala geçerli olanları ekle
    final_groups.extend(valid_existing)
    
    valid_ids = {str(g.get('id')) for g in valid_existing}
    
    if len(final_groups) < 100:
        # 100'e tamamlamak için API'den gelen diğer grupları ekle
        logger.info(f"Grup sayısı 100'den az ({len(final_groups)}), tamamlanıyor...")
        for g in api_groups:
            gid = str(g.get('id'))
            if gid not in valid_ids:
                # Basitleştirilmiş grup verisi
                new_g = {
                    "name": g.get('name', g.get('subject', 'Bilinmeyen Grup')),
                    "id": gid
                }
                final_groups.append(new_g)
                valid_ids.add(gid)
            
            if len(final_groups) >= 100:
                break
    elif len(final_groups) > 100:
        # 100'den fazlaysa 100'e düşür
        logger.info(f"Grup sayısı 100'den fazla ({len(final_groups)}), 100'e düşürülüyor...")
        final_groups = final_groups[:100]
        
    logger.info(f"Sonuç: Toplam {len(final_groups)} grup kaydedilecek.")
    
    # 5. Kaydet
    if len(final_groups) > 0:
        # Yedek al
        backup_file = chat_groups_file + ".bak"
        try:
            if os.path.exists(chat_groups_file):
                import shutil
                shutil.copy2(chat_groups_file, backup_file)
                logger.info(f"Yedek oluşturuldu: {backup_file}")
        except Exception as e:
            logger.warning(f"Yedek oluşturulamadı: {e}")
            
        save_json_safe(chat_groups_file, final_groups)
        logger.info("data/chat_groups.json başarıyla güncellendi.")
    else:
        logger.warning("Kaydedilecek grup bulunamadı. Dosya değiştirilmedi.")

if __name__ == "__main__":
    sync_groups_to_100()
