#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integration wrapper: Use TextGenParser in production
This replaces the complex GroupBasedParser with clean text generation approach
"""

import sys
import os
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

class ProductionParser:
    """
    Production-ready parser using text generation.
    Drop-in replacement for GroupBasedParser.
    """
    
    def __init__(self):
        self.parser = TextGenParser()
    
    def parse_message(self, message: str, group_name: str = None):
        """Parse message - compatible with GroupBasedParser API."""
        return self.parser.parse(message)
    
    def parse_messages(self, messages: list):
        """Parse multiple messages."""
        all_results = []
        for msg in messages:
            results = self.parse_message(msg)
            all_results.extend(results)
        return all_results


# PRODUCTION TEST
if __name__ == "__main__":
    parser = ProductionParser()
    
    # Test 1: Simple lines
    test1 = """İSTANBUL PENDİK - ANKARA YENİMAHALLE TIR BRANDALI 26 TON 0532 555 12 34
MERSİN AKDENİZ - İZMİR TIRE AÇIK 15 TON PALET
GAZİANTEP ŞEHİTKAMİL - DİYARBAKIR SUR KOMPLE 20 TON"""
    
    print("=" * 80)
    print("PRODUCTION PARSER TEST")
    print("=" * 80)
    print(f"\n{test1}\n")
    print("-" * 80)
    
    results = parser.parse_message(test1)
    
    print(f"\n[OK] Parsed {len(results)} routes\n")
    
    for i, r in enumerate(results, 1):
        print(f"[Route {i}]")
        print(f"  {r['nereden_il']}/{r['nereden_ilce']} -> {r['nereye_il']}/{r['nereye_ilce']}")
        print(f"  Kasa: {', '.join(r['kasa_tipi'])}")
        if r.get('telefon'):
            print(f"  Tel: {r['telefon']}")
    
    # Validation
    print("\n" + "=" * 80)
    print("VALIDATION")
    print("=" * 80)
    
    mersin_found = any(r['nereden_il'] == 'MERSİN' for r in results)
    gazi_found = any(r['nereden_il'] in ['GAZİANTEP', 'GAZIANTEP'] for r in results)
    tire_correct = any(
        r['nereye_ilce'] == 'TİRE' and r['nereye_il'] == 'İZMİR' 
        for r in results
    )
    
    print(f"{'[OK]' if mersin_found else '[FAIL]'} MERSİN as origin")
    print(f"{'[OK]' if gazi_found else '[FAIL]'} GAZİANTEP as origin")
    print(f"{'[OK]' if tire_correct else '[FAIL]'} TIRE in İZMİR")
    print(f"{'[OK]' if len(results) == 3 else '[FAIL]'} 3 routes (got {len(results)})")
    
    if all([mersin_found, gazi_found, tire_correct, len(results) == 3]):
        print("\n[SUCCESS] PRODUCTION READY!")
    
    # Save
    import json
    with open('production_parser_test.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"[FILE] Results saved: production_parser_test.json")
