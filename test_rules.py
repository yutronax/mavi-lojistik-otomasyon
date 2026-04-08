import sys
import os
sys.path.insert(0, os.getcwd())
from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_messages = [
    "ADANA KARATAŞ MISIR 🌽 KISA DORSA",
    "Bursa Mustafakemalpaşa Esenyurt+Eyüp tır",
    "TERMOKİN TIR-PALETLİ GIDA"
]

for msg in test_messages:
    print(f"\nMessage: {msg}")
    rules = matcher.get_relevant_rules(msg)
    print(f"Found {len(rules)} relevant rules:")
    for r in rules:
        print(f"  - {r['pattern']} -> {r['output']}")
