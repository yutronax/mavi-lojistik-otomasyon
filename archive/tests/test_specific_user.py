
import sys
import os
import json

# Absolute path to ensure we're looking at the right project directory
sys.path.insert(0, r"c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik")

from tools.submit_approved_loads import YukBuradaSubmitter

def test_number_merge(phone):
    print(f"\n--- TESTING SMART MERGE FOR: {phone} ---")
    submitter = YukBuradaSubmitter()
    
    # Bu fonksiyon tüm varyantları tarayacak, varsa mükerrerleri silecek
    # ve en iyi hesabı (varsa isimli olanı) seçecek.
    result = submitter.get_or_create_user_with_merge(phone)
    
    if result:
        print("\n[SUCCESS] Smart logic finished:")
        print(f"Selected Primary ID: {result.get('user_id')}")
        print(f"Selected Phone Variant: {result.get('phone')}")
        print(f"Final Name in System: {result.get('fullName')}")
    else:
        print("\n[FAILED] Could not process number.")

if __name__ == "__main__":
    target = "05309429862"
    test_number_merge(target)
