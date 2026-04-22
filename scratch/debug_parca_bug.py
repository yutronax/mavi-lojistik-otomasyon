
import sys
import os
import re

# Simulate the normalization and regex from vehicle_type_matcher.py
def normalize(text):
    text = text.upper()
    text = re.sub(r'[\-\.\,\/\+\(\)\[\]]', '', text)
    return text.strip()

def test_regex(message):
    norm_message = normalize(message)
    print(f"Original: {message}")
    print(f"Normalized: {norm_message}")
    
    # The regex from line 367 of vehicle_type_matcher.py
    regex = r'(\d+)\s*(?:PALET|PLT|PALETLİ|PALETLI|TON|TONLUK|T)'
    matches = re.findall(regex, norm_message)
    print(f"Matches: {matches}")
    
    for count_str in matches:
        count = int(count_str)
        if "PALET" in norm_message or "PLT" in norm_message:
             if count >= 7:
                 print("Result: PARÇA (due to PALET >= 7)")
        else:
             if count < 10:
                 print("Result: PARÇA (due to TON/T < 10)")

test_regex("1 TIR")
test_regex("2 TIR")
test_regex("İZMİR İSTANBUL 1 TIR")
