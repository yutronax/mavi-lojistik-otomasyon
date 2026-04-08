import json

def verify_v2(v1_path, v2_path):
    with open(v1_path, 'r', encoding='utf-8') as f:
        v1 = json.load(f)
    with open(v2_path, 'r', encoding='utf-8') as f:
        v2 = json.load(f)
    
    # Map by pattern
    v1_map = {r['orjinal mesajdaki'].strip().upper(): r for r in v1}
    v2_map = {r['orjinal mesajdaki'].strip().upper(): r for r in v2}
    
    targets = ["TIR", "1360 FRİGO", "KIRKAYAK", "AÇIK", "YÜKÜMÜZ", "KISA DORSE", "PICKUP"]
    
    report = []
    for t in targets:
        r1 = v1_map.get(t.upper())
        r2 = v2_map.get(t.upper())
        
        if r1 and r2:
            report.append({
                "pattern": t,
                "v1": {"priority": r1['priority'], "output": r1['kesin_cikti']},
                "v2": {"priority": r2['priority'], "output": r2['kesin_cikti']}
            })
            
    return report

if __name__ == "__main__":
    v1 = 'data/yuk_tipi.json'
    v2 = 'data/yuk_tipi_v2.json'
    results = verify_v2(v1, v2)
    print(json.dumps(results, indent=2, ensure_ascii=False))
