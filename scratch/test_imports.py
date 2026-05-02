import sys
import os

# Proje kök dizinini ekle
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    print("Test: ServerControlPage import...")
    from src.gui.pages.server_control import ServerControlPage
    print("OK.")

    print("Test: ManagementCenterPage import...")
    from src.gui.pages.management_center import ManagementCenterPage
    print("OK.")

    print("Test: flet_app import...")
    # main fonksiyonunu import etmeyi deneyelim
    from src.gui.flet_app import main
    print("OK.")

    print("\nBütün modüller başarıyla yüklendi.")
except Exception as e:
    print(f"\nHATA: {e}")
    sys.exit(1)
