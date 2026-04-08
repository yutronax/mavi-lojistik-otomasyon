
import os
import sys
import json
import hashlib
from datetime import datetime, timedelta

# Project root setup
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Ensure UTF-8 output
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.utils.phone_utils import is_phone_in_list
from src.utils.vehicle_type_matcher import VehicleTypeMatcher
from src.services.data_service import DataService

def test_blacklist_filter():
    print("\n--- Test 1: Blacklist Filter ---")
    blacklist = ["905001112233", "905554443322"]
    
    test_cases = [
        ("905001112233@c.us", True),   # Blacklisted
        ("905001112244@c.us", False),  # Not blacklisted
        ("905554443322", True),        # Blacklisted
    ]
    
    all_passed = True
    for phone, expected in test_cases:
        result = is_phone_in_list(phone, blacklist)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"Phone: {phone:20} | Expected: {expected} | Got: {result} | {status}")
        if result != expected: all_passed = False
    return all_passed

def test_yuk_rules_matching():
    print("\n--- Test 2: Yuk Rules Matching (VehicleTypeMatcher) ---")
    matcher = VehicleTypeMatcher()
    
    test_cases = [
        {
            "msg": "İSTANBUL PENDİK - ANKARA TIR BRANDALI 26 TON",
            "expected_vehicle": "1360", # Standard TIR maps to 1360
            "expected_kasa": "KAPALI"   # Brandalı maps to Kapalı in rules
        },
        {
            "msg": "BUGDAY YUKU VAR 26 TON",
            "expected_vehicle": "860", # Special rule for Buğday
            "expected_load": "DÖKME"
        },
        {
            "msg": "10 PALET MALZEME",
            "expected_load": "PARÇA" # Rule for > 7 palet
        },
        {
            "msg": "5 TON DEMİR",
            "expected_load": "PARÇA" # Rule for < 10 ton
        }
    ]
    
    all_passed = True
    for case in test_cases:
        match = matcher.find_match(case['msg'])
        print(f"\nMessage: {case['msg']}")
        if not match:
            print("  ❌ NO MATCH FOUND")
            all_passed = False
            continue
            
        print(f"  Result: {match}")
        
        passed = True
        if 'expected_vehicle' in case:
            if case['expected_vehicle'] not in match.get('ARAÇ TİPİ', ''):
                print(f"  ❌ Expected Vehicle: {case['expected_vehicle']}, Got: {match.get('ARAÇ TİPİ')}")
                passed = False
        
        if 'expected_kasa' in case:
            if case['expected_kasa'] not in match.get('KASA TİPİ', ''):
                print(f"  ❌ Expected Kasa: {case['expected_kasa']}, Got: {match.get('KASA TİPİ')}")
                passed = False

        if 'expected_load' in case:
            if case['expected_load'] not in match.get('YÜKÜN TİPİ', ''):
                print(f"  ❌ Expected Load: {case['expected_load']}, Got: {match.get('YÜKÜN TİPİ')}")
                passed = False
        
        if passed: print("  ✅ MATCH CORRECT")
        else: all_passed = False
        
    return all_passed

def test_data_service_filters():
    print("\n--- Test 3: DataService Load Filters (Blacklist & Foreign Location) ---")
    data_service = DataService(PROJECT_ROOT)
    
    # Create a temp file for testing
    test_file = os.path.join(PROJECT_ROOT, "data", "test_onaylanmamis.json")
    data_service.onaylanmamis_file = test_file
    
    # Test Data
    now = datetime.now()
    old_time = now - timedelta(days=3)
    
    test_data = [
        {
            "message_id": "msg_ok",
            "phone": "9050011122xx",
            "body": "Normal Message",
            "timestamp": now.timestamp()
        },
        {
            "message_id": "msg_blacklisted",
            "phone": "905001112233", # In blacklist according to test_blacklist_filter if we set it
            "body": "Blacklisted Message",
            "timestamp": now.timestamp()
        },
        {
            "message_id": "msg_foreign",
            "invalid_location": True,
            "body": "Foreign Message",
            "timestamp": now.timestamp()
        },
        {
            "message_id": "msg_old",
            "body": "Old Message",
            "timestamp": old_time.timestamp()
        }
    ]
    
    # Save test data
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(test_data, f)
        
    # Mock load_blacklist to return our test blacklist
    data_service.load_blacklist = lambda: ["905001112233"]
    
    # Load messages
    messages = data_service.load_unprocessed_messages(hours_back=48)
    
    print(f"Initial messages: {len(test_data)}")
    print(f"Filtered messages: {len(messages)}")
    
    results = {
        "msg_ok": "msg_ok" in messages,
        "msg_blacklisted": "msg_blacklisted" not in messages,
        "msg_foreign": "msg_foreign" not in messages,
        "msg_old": "msg_old" not in messages
    }
    
    all_passed = True
    for key, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"Filter {key:15}: {status}")
        if not passed: all_passed = False
        
    # Cleanup
    if os.path.exists(test_file): os.remove(test_file)
    
    return all_passed

def test_existing_ids_filter():
    print("\n--- Test 4: Existing IDs Filter (Whapi Fetcher Logic) ---")
    existing_ids = {"msg_1", "msg_2"}
    new_messages = [
        {"id": "msg_1", "body": "Same 1"},
        {"id": "msg_2", "body": "Same 2"},
        {"id": "msg_3", "body": "New 3"}
    ]
    
    fetched = [m for m in new_messages if m['id'] not in existing_ids]
    
    print(f"Total New: {len(new_messages)}")
    print(f"Filtered (New Only): {len(fetched)}")
    
    passed = len(fetched) == 1 and fetched[0]['id'] == "msg_3"
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"Result: {status}")
    return passed

if __name__ == "__main__":
    print("🚀 STARTING FILTER TESTS")
    results = [
        test_blacklist_filter(),
        test_yuk_rules_matching(),
        test_data_service_filters(),
        test_existing_ids_filter()
    ]
    
    if all(results):
        print("\n✨ ALL TESTS PASSED SUCCESSFULLY!")
    else:
        print("\n⚠️ SOME TESTS FAILED. CHECK LOGS.")
        sys.exit(1)
