import json
import os

def migrate_rules_v2(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        rules = json.load(f)
    
    new_rules = []
    
    # Priority Bands
    P1_COMBO = 4500
    P2_STRONG_ENTITY_COMBO = 3500
    P3_STRONG_SINGLE_ENTITY = 2500
    P4_TYPED_GENERIC = 1500
    P5_FALLBACK_DEFAULT = 500
    P6_STOPWORD_IGNORE = 50
    
    # Semantic Groups for Classification
    strong_entities = ["TERMOKİN", "TERMOKIN", "LOWBED", "DAMPERLİ", "DAMPERLI", "FRİGO", "FRIGO", "SOĞUTUCU", "SOGUTUCU"]
    medium_entities = ["KIRKAYAK", "40 AYAK", "40AYAK", "10 TEKER", "10TEKER", "ATEGO", "JUMBO", "SAL DORSE", "SALDORSE"]
    generics = ["AÇIK", "ACIK", "KAPALI", "TENTELİ", "TENTELI", "TENTE", "PALETLİ", "PALETLI", "DÖKME", "DOKME"]
    fallbacks = ["TIR", "1360", "860", "KAMYON", "KAMYONET", "PIKUP", "PICKUP", "PANELVAN"]
    stopwords = ["YÜKÜMÜZ", "YUKUMUZ", "ARANIYOR", "HEMEN", "LÜTFEN"]

    for rule in rules:
        pattern = str(rule.get("orjinal mesajdaki", "")).strip()
        priority = rule.get("priority", 0)
        output = rule.get("kesin_cikti", {})
        
        # 1. Standardize Output Labels
        new_output = {}
        for k, v in output.items():
            # ARAÇ TİPİ Normalization
            if k == "ARAÇ TİPİ":
                if isinstance(v, list):
                    v = [str(x).replace("40 AYAK", "KIRKAYAK").replace("PICKUP", "KAMYONET").replace("PIKUP", "KAMYONET") for x in v]
                else:
                    v = str(v).replace("40 AYAK", "KIRKAYAK").replace("PICKUP", "KAMYONET").replace("PIKUP", "KAMYONET")
            
            # KASA TİPİ Normalization
            if k == "KASA TİPİ":
                if isinstance(v, list):
                    v = [str(x).replace("ACIK", "AÇIK").replace("TENTELI", "KAPALI").replace("TENTELİ", "KAPALI") for x in v]
                else:
                    v = str(v).replace("ACIK", "AÇIK").replace("TENTELI", "KAPALI").replace("TENTELİ", "KAPALI")
            
            new_output[k] = v

        # 2. Determine New Priority
        new_p = priority # Default is keep old if not matched
        pattern_up = pattern.upper()
        tokens = pattern_up.split()
        
        # P6: Stopwords
        if any(sw in pattern_up for sw in stopwords):
            new_p = P6_STOPWORD_IGNORE
        
        # P1: Exact Combos (Multiple significant words)
        elif len(tokens) >= 2 and any(e in pattern_up for e in strong_entities + medium_entities + generics):
            new_p = P1_COMBO
            
        # P2: Strong Entity combos or specific ones
        elif any(e in pattern_up for e in strong_entities):
            new_p = P3_STRONG_SINGLE_ENTITY # Single strong entity
            if len(tokens) >= 2:
                new_p = P2_STRONG_ENTITY_COMBO # Strong entity with something else
        
        # P3: Medium entities
        elif any(e in pattern_up for e in medium_entities):
            new_p = P3_STRONG_SINGLE_ENTITY
            
        # P4: Generics
        elif any(g in pattern_up for g in generics):
            new_p = P4_TYPED_GENERIC
            
        # P5: Fallbacks
        elif any(f in pattern_up for f in fallbacks):
            new_p = P5_FALLBACK_DEFAULT
            
        # Specific override for TIR if alone
        if pattern_up == "TIR":
            new_p = 100 # Very low for base TIR
            
        if pattern_up == "1360" or pattern_up == "13.60":
            new_p = 120 # Low for base 1360

        # Create new rule object
        new_rule = {
            "orjinal mesajdaki": pattern,
            "priority": new_p,
            "kesin_cikti": new_output,
            "notlar": rule.get("notlar", "") + " [Migrated v2]"
        }
        
        # Preserve other fields if any
        for key in rule:
            if key not in new_rule:
                new_rule[key] = rule[key]
                
        new_rules.append(new_rule)

    # Save v2
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(new_rules, f, ensure_ascii=False, indent=2)
        
    return len(new_rules)

if __name__ == "__main__":
    src = 'data/yuk_tipi.json'
    dest = 'data/yuk_tipi_v2.json'
    count = migrate_rules_v2(src, dest)
    print(f"Successfully migrated {count} rules to v2.")
