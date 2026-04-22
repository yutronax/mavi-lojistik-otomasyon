
import sys
import os
import re

def normalize(text):
    text = text.upper()
    text = re.sub(r'[\-\.\,\/\+\(\)\[\]]', '', text)
    return text.strip()

def test_regex(message, regex):
    norm_message = normalize(message)
    print(f"Original: {message}")
    print(f"Normalized: {norm_message}")
    print(f"Regex: {regex}")
    
    matches = re.findall(regex, norm_message)
    print(f"Matches: {matches}")
    
    for match in matches:
        # If the regex has multiple groups or just one
        count_str = match[0] if isinstance(match, tuple) else match
        count = int(count_str)
        if "PALET" in norm_message or "PLT" in norm_message:
             if count >= 7:
                 print("Result: PARÇA (due to PALET >= 7)")
        else:
             if count < 10:
                 print("Result: PARÇA (due to TON/T < 10)")
    print("-" * 20)

# Current faulty regex
faulty_regex = r'(\d+)\s*(?:PALET|PLT|PALETLİ|PALETLI|TON|TONLUK|T)'
print("=== FAULTY REGEX ===")
test_regex("1 TIR", faulty_regex)

# Proposed fixed regex
# Use \b for T to ensure it's a standalone unit or end of word, and NOT start of TIR
# Actually, (\d+)\s*T\b would match "1 T" but not "1 TIR"
fixed_regex = r'(\d+)\s*(?:PALET|PLT|PALETLİ|PALETLI|TON|TONLUK|T\b)'
print("=== FIXED REGEX ===")
test_regex("1 TIR", fixed_regex)
test_regex("1 T", fixed_regex)
test_regex("1 TON", fixed_regex)
test_regex("1-T", fixed_regex) # Normalization removes - so it becomes 1T
