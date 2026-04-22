import json
import random
import sys
import os
import asyncio
import time

# Add project root to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

async def sample_and_parse_parallel():
    json_path = os.path.join('data', 'mesajlar.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    messages = [m['body'] for m in data.get('messages', []) if m.get('body') and len(m['body']) > 10]
    
    # Pick 10 random messages
    samples = random.sample(messages, 10) if len(messages) >= 10 else messages
    
    parser = TextGenParser()
    
    print(f"PARALEL İŞLEME BAŞLIYOR: {len(samples)} mesaj aynı anda işlenecek...")
    start_time = time.time()
    
    try:
        # Use the NEW parallel batch engine
        batch_results = await parser.parse_batch(samples)
        
        results = []
        for i, (msg, parsed) in enumerate(zip(samples, batch_results)):
            results.append({
                "original_message": msg,
                "parsed_routes": parsed
            })
            
    except Exception as e:
        print(f"Kritik Hata: {e}")
        results = [{"error": str(e)}]
            
    end_time = time.time()
    elapsed = end_time - start_time
    
    # Output final JSON
    output_path = os.path.join('scratch', 'parallel_parsed_results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nBİTTİ! Toplam Süre: {elapsed:.2f} saniye")
    print(f"Mesaj başına ortalama süre: {elapsed/len(samples):.2f} saniye")
    print(f"Sonuçlar kaydedildi: {output_path}")

if __name__ == "__main__":
    asyncio.run(sample_and_parse_parallel())
