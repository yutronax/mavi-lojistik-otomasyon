import json
import os
import re

def analyze_rules(file_path):
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
        
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            rules = json.load(f)
        except Exception as e:
            return {"error": str(e)}
    
    analysis = {
        "priority_stats": {},
        "canonical_labels": {
            "ARAÇ TİPİ": set(),
            "KASA TİPİ": set(),
            "YÜKÜN TİPİ": set()
        },
        "all_patterns": {},
        "inconsistencies": []
    }
    
    # Track pattern occurrences
    pattern_count = {}
    
    for i, rule in enumerate(rules):
        pattern = str(rule.get("orjinal mesajdaki", "")).upper().strip()
        priority = rule.get("priority", 0)
        output = rule.get("kesin_cikti", {})
        
        # Priority stats
        p_str = str(priority)
        analysis["priority_stats"][p_str] = analysis["priority_stats"].get(p_str, 0) + 1
        
        # Canonical labels
        for k in ["ARAÇ TİPİ", "KASA TİPİ", "YÜKÜN TİPİ"]:
            val = output.get(k)
            if val:
                if isinstance(val, list):
                    for v in val:
                        analysis["canonical_labels"][k].add(str(v).strip().upper())
                else:
                    analysis["canonical_labels"][k].add(str(val).strip().upper())
                    
        # Find inconsistencies
        if pattern in analysis["all_patterns"]:
            prev_rule = analysis["all_patterns"][pattern]
            if prev_rule["output"] != output:
                # Same pattern, different output
                analysis["inconsistencies"].append({
                    "pattern": pattern,
                    "case1": {"priority": prev_rule["priority"], "output": prev_rule["output"]},
                    "case2": {"priority": priority, "output": output}
                })
        else:
            analysis["all_patterns"][pattern] = {"priority": priority, "output": output}

    # High priority generic terms check
    dangerous_patterns = ["TIR", "1360", "860", "AÇIK", "KAPALI", "PALET", "DÖKME", "FRİGO", "DAMPERLİ", "KAMYON", "KAMYONET", "KIRKAYAK", "40 AYAK"]
    analysis["dangerous"] = []
    
    for dp in dangerous_patterns:
        norm_dp = dp.upper()
        if norm_dp in analysis["all_patterns"]:
            p = analysis["all_patterns"][norm_dp]["priority"]
            if p >= 500: # Any significant priority for a single word is potentially dangerous
                analysis["dangerous"].append({"pattern": norm_dp, "priority": p})
    
    # Sort for final output
    for key in analysis["canonical_labels"]:
        analysis["canonical_labels"][key] = sorted(list(analysis["canonical_labels"][key]))
        
    return analysis

if __name__ == "__main__":
    file_path = 'c:/Users/YUSUF ÇİNAR/OneDrive/Belgeler/Masaüstü/projelerim/maviLojistik/data/yuk_tipi.json'
    results = analyze_rules(file_path)
    
    # Output only summary info to prevent huge log files
    summarized_results = {
        "priority_stats": results["priority_stats"],
        "canonical_labels": results["canonical_labels"],
        "dangerous": results["dangerous"],
        "total_rules": len(results.get("all_patterns", {})),
        "inconsistency_count": len(results.get("inconsistencies", [])),
        "inconsistencies_sample": results.get("inconsistencies", [])[:20]
    }
    
    print(json.dumps(summarized_results, indent=2, ensure_ascii=False))
