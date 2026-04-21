import os
import re

def update_prompt():
    file_path = r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\src\fetchers\mavi_whap.py'
    
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
    
    new_prompt_code = '''    # Güçlendirilmiş Yapılandırılmış İstem (Llama 3.1 Optimizasyonu)
    prompt = f"""
Sana verilen lojistik mesajındaki sevkiyat bilgilerini analiz et ve JSON formatında döndür.

### ANALİZ ADIMLARI:
1. GÜZERGAH TESPİTİ: "→", "=>", "-", "/", "den", "dan", "istikamet", "yönü" gibi ifadeleri bul.
2. COĞRAFİ DOĞRULAMA: 
   - İlçe belirtilmişse, o ilçenin BAĞLI OLDUĞU İLİ bul (Örn: Lüleburgaz -> KIRKLARELİ, Gebze -> KOCAELİ, İnegöl -> BURSA).
   - İl ve İlçe isimlerini mutlaka BÜYÜK HARFLE yaz.
3. ARAÇ VE KASA TİPİ: Mesajdaki anahtar kelimelerden (13.60, Tır, Onteker, Kamyon, Açık, Tenteli, Frigo vb.) tespiti yap.
4. ÇOKLU SEVKİYAT: Mesajda birden fazla rota varsa her biri için ayrı JSON objesi oluştur.

### ÇIKTI ŞEMASI (JSON):
{{
  "shipments": [
    {{
      "isim": "Firma veya Kişi Adı (Yoksa 'BİLİNMİYOR')",
      "nereden_il": "KALKIŞ İLİ (Büyük Harf)",
      "nereden_ilce": "KALKIŞ İLÇESİ (Büyük Harf)",
      "nereye_il": "VARIŞ İLİ (Büyük Harf)",
      "nereye_ilce": "VARIŞ İLÇESİ (Büyük Harf)",
      "arac_tipi": ["1360", "TIR", "ONTEKER", "KAMYON", "KAMYONET" içinden en uygun olanlar],
      "kasa_tipi": ["AÇIK", "KAPALI", "TENTELİ", "FRİGO", "TERMOKİN" içinden en uygun olanlar],
      "yuk_tipi": ["KOMPLE", "PARÇA"],
      "fiyat": "Fiyat bilgisi veya 'SORUNUZ'",
      "telefon": "Tüm telefonların listesi (Virgülle ayrılmış)",
      "aciklama": "Ek bilgiler (Emoji içermez)",
      "message_id": "{message_id}"
    }}
  ]
}}

### GEÇERLİ İLLER (Sadece Bunları Kullan):
{iller_listesi}

### İŞLENECEK MESAJ:
"{message_body}"

SADECE JSON DÖNDÜR. BAŞKA METİN EKLEME.
"""'''
    
    start_idx = -1
    end_idx = -1
    
    for i, line in enumerate(lines):
        if 'prompt = f"""' in line:
            start_idx = i
        if start_idx != -1 and '"""' in line and i > start_idx:
            # Check if this is the end of the prompt block
            # In the original file, the prompt ends with """
            # followed by some logic.
            # Looking at the file, the next line after prompt is usually 'try:' or empty
            end_idx = i
            break
            
    if start_idx != -1 and end_idx != -1:
        new_lines = lines[:start_idx] + [new_prompt_code + '\n'] + lines[end_idx+1:]
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"Successfully updated prompt between lines {start_idx+1} and {end_idx+1}")
    else:
        print(f"Could not find prompt block. Start: {start_idx}, End: {end_idx}")

if __name__ == "__main__":
    update_prompt()
