import os
import json
import shutil
from pathlib import Path

# Get root path correctly
def get_root_path():
    return Path("c:/Users/YUSUF ÇİNAR/OneDrive/Belgeler/Masaüstü/projelerim/maviLojistik")

def reset_today_data():
    root = get_root_path()
    data_dir = root / 'data'
    print(f"Veri dizini: {data_dir}")
    
    files_to_reset = [
        'onaylanmamis_ayristirilmis.json',
        'handled_ids.json',
        'processed_contents.json'
    ]
    
    for filename in files_to_reset:
        file_path = data_dir / filename
        if file_path.exists():
            # Yedekle
            backup_path = data_dir / f"{filename}.reset_bak"
            try:
                shutil.copy2(file_path, backup_path)
                print(f"Yedek alındı: {filename}.reset_bak")
            except Exception as e:
                print(f"Yedek alınamadı (belki dosya açık?): {e}")
            
            # İçeriği sıfırla
            empty_data = [] if filename == 'onaylanmamis_ayristirilmis.json' else {}
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(empty_data, f)
                print(f"Sıfırlandı: {filename}")
            except Exception as e:
                print(f"Sıfırlanamadı (Dosya kullanımda olabilir): {e}")
        else:
            print(f"Dosya bulunamadı: {filename}")

if __name__ == "__main__":
    reset_today_data()
