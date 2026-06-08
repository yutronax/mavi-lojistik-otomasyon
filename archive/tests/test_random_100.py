#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Rastgele 100 Test Scripti

Sistemin kararlılığını ve fuzzy matching performansını ölçmek için
rastgele 100 mahalle seçip test eder.
"""

import os
import sys
import json
import random
import time

# UTF-8 encoding zorlaması
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Proje kök dizinini ekle
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(current_dir, 'src'))

from src.utils.location_helper import LocationHelper

def bozuk_yazim_olustur(text: str) -> str:
    """Metinde rastgele 1 harf hatası oluşturur"""
    if len(text) < 4:
        return text
    
    chars = list(text)
    pos = random.randint(0, len(chars) - 1)
    choice = random.choice(['sil', 'degistir'])
    
    if choice == 'sil':
        # Bir harfi sil
        del chars[pos]
    else:
        # Bir harfi değiştir
        chars[pos] = random.choice('abcdefghijklmnopqrstuvwxyz')
        
    return "".join(chars)

def ana_test():
    print("=" * 60)
    print("RASTGELE 100 STRES TESTİ")
    print("=" * 60)
    
    # Veriyi yükle
    data_dir = os.path.join(current_dir, 'data')
    json_path = os.path.join(data_dir, 'il_ilçe_mahalle.json')
    
    print("Veri yukleniyor...")
    with open(json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    helper = LocationHelper(data_dir)
    # İndeksi önbelleğe al (ilk aramada yavaşlamasın)
    print("Indeks olusturuluyor...")
    helper.build_mahalle_index()
    
    # Tüm mahalle havuzunu oluştur
    havuz = []
    for il_item in raw_data:
        il = il_item['il']
        for ilce_item in il_item.get('ilceler', []):
            ilce = ilce_item['ilce']
            for mah in ilce_item.get('mahalleler', []):
                # Sadece yeterince uzun ve benzersiz isimleri al (test kalitesi için)
                if len(mah) > 4:
                    havuz.append((il, ilce, mah))
    
    total_mahalle = len(havuz)
    print(f"Havuzda {total_mahalle} mahalle var.")
    
    # ---------------------------------------------------------
    # TEST 1: 50 TAM DOĞRU EŞLEŞME
    # ---------------------------------------------------------
    print("\n" + "-" * 60)
    print("TEST 1: 50 Rastgele DOĞRU Yazim Testi")
    print("-" * 60)
    
    test_set_1 = random.sample(havuz, 50)
    success_1 = 0
    
    start_time = time.time()
    for i, (expect_il, expect_ilce, mahalle) in enumerate(test_set_1):
        result = helper.search_location(mahalle)
        
        status = "[FAIL]"
        found_text = "BULUNAMADI"
        
        if result:
            found_il, found_ilce = result
            # İli veya ilçesi doğruysa kabul et (bazı mahalle adları çok yaygın olabilir, "Merkez" gibi)
            if found_il == expect_il and found_ilce == expect_ilce:
                status = "[OK]"
                success_1 += 1
                found_text = f"{found_il}/{found_ilce}"
            else:
                status = "[DIFF]" # Başka bir ildeki aynı isimli mahalleyi bulmuş olabilir
                found_text = f"{found_il}/{found_ilce} (Beklenen: {expect_il}/{expect_ilce})"
                # Bu durumda aslında sistem buldu ama şansımıza başka ili buldu
                # Mahalle ismi unique değilse bu normaldir.
                # Test başarısı için bunu "Warning" sayalım ama success artırmayalım.
        
        print(f"{i+1:02d}. {status} {mahalle:<30} -> {found_text}")
        
    duration_1 = time.time() - start_time
    print(f"\nSonuc: {success_1}/50 Tam İsabet ({duration_1:.2f}sn)")

    # ---------------------------------------------------------
    # TEST 2: 50 HATALI YAZIM (FUZZY)
    # ---------------------------------------------------------
    print("\n" + "-" * 60)
    print("TEST 2: 50 Rastgele HATALI Yazim (Fuzzy) Testi")
    print("-" * 60)
    
    # Yeni bir set seç
    remaining_pool = [x for x in havuz if x not in test_set_1]
    if len(remaining_pool) < 50:
        remaining_pool = havuz # Yeterince kalmadıysa havuzu sıfırla
        
    test_set_2 = random.sample(remaining_pool, 50)
    success_2 = 0
    
    start_time = time.time()
    for i, (expect_il, expect_ilce, mahalle) in enumerate(test_set_2):
        bozuk_mahalle = bozuk_yazim_olustur(mahalle)
        result = helper.search_location(bozuk_mahalle)
        
        status = "[FAIL]"
        found_text = "BULUNAMADI"
        
        if result:
            found_il, found_ilce = result
            if found_il == expect_il and found_ilce == expect_ilce:
                status = "[OK]"
                success_2 += 1
                found_text = f"{found_il}/{found_ilce}"
            else:
                status = "[DIFF]"
                found_text = f"{found_il}/{found_ilce} (Beklenen: {expect_il}/{expect_ilce})"
        
        # Fuzzy testinde sadece başarılı olanları veya DIFF olanları göstermek daha anlamlı olabilir
        # ama hepsini gösterelim
        print(f"{i+1:02d}. {status} {bozuk_mahalle:<30} (Asli: {mahalle}) -> {found_text}")
        
    duration_2 = time.time() - start_time
    print(f"\nSonuc: {success_2}/50 Kurtarıldı ({duration_2:.2f}sn)")
    
    # ---------------------------------------------------------
    # TEST 3: 50 İL + MAHALLE KOMBİNASYONU (FİLTRE TESTİ)
    # ---------------------------------------------------------
    print("\n" + "-" * 60)
    print("TEST 3: 50 İl + Mahalle (Filtreli Arama) Testi")
    print("-" * 60)
    
    # 25 tane Test 1'den (Doğru), 25 tane Test 2'den (Hatalı) alalım
    test_set_3 = test_set_1[:25] + test_set_2[:25]
    success_3 = 0
    
    start_time = time.time()
    for i, (expect_il, expect_ilce, mahalle) in enumerate(test_set_3):
        # Sorguyu "İL MAHALLE" şeklinde oluştur
        # Örn: "ADANA Cumhuriyet" veya "ADANA Jumhuriyet" (eğer hatalıysa)
        
        # Test 2 setinden gelenler için bozuk yazım kullanalım
        if i >= 25: 
            query_mahalle = bozuk_yazim_olustur(mahalle)
        else:
            query_mahalle = mahalle
            
        full_query = f"{expect_il} {query_mahalle}"
        
        result = helper.search_location(full_query)
        
        status = "[FAIL]"
        found_text = "BULUNAMADI"
        
        if result:
            found_il, found_ilce = result
            # Burada ilçe de kesinlikle eşleşmeli çünkü ili filtre olarak verdik!
            if found_il == expect_il and found_ilce == expect_ilce:
                status = "[OK]"
                success_3 += 1
                found_text = f"{found_il}/{found_ilce}"
            else:
                status = "[DIFF]"
                found_text = f"{found_il}/{found_ilce} (Beklenen: {expect_il}/{expect_ilce})"
        
        print(f"{i+1:02d}. {status} {full_query:<35} -> {found_text}")

    duration_3 = time.time() - start_time
    print(f"\nSonuc: {success_3}/50 Tam İsabet ({duration_3:.2f}sn)")

    print("\n" + "=" * 60)
    print(f"GENEL BASARI: {success_1 + success_2 + success_3}/150")
    print("=" * 60)

if __name__ == "__main__":
    try:
        ana_test()
    except Exception as e:
        print(f"HATA: {e}")
