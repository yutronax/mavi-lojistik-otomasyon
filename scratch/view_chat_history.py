import os
import glob
from datetime import datetime

def get_activity_logs():
    log_dir = r"c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\memory\logs"
    log_files = glob.glob(os.path.join(log_dir, "activity_log_*.md"))
    log_files.sort(reverse=True) # En yeni en üstte
    return log_files

def main():
    print("Mavi Lojistik - Proje Gecmisi (Aktivite Loglari)\n")
    logs = get_activity_logs()
    
    if not logs:
        print("Geçmiş log kaydı bulunamadı.")
        return

    for log_path in logs:
        file_name = os.path.basename(log_path)
        print(f"--- {file_name} ---")
        try:
            # Farklı encoding kombinasyonlarını dene
            content = None
            for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1254']:
                try:
                    with open(log_path, 'r', encoding=encoding) as f:
                        content = f.readlines()
                        break
                except (UnicodeDecodeError, UnicodeEncodeError):
                    continue
            
            if content is None:
                print(f"Hata: {file_name} okunurken kodlama sorunu yasandi.")
                continue

            entry_count = 0
            for line in content:
                if line.startswith("## ["):
                    entry_count += 1
                if entry_count > 5:
                    print("\n[Daha eski kayitlar icin dosyayi dogrudan acabilirsiniz...]")
                    break
                # Terminalde yazdirilamayan karakterleri temizle
                clean_line = line.encode('ascii', 'ignore').decode('ascii').rstrip()
                if clean_line:
                    print(clean_line)
            print("\n")
        except Exception as e:
            print(f"Hata: {file_name} okunamadı. {e}")

if __name__ == "__main__":
    main()
