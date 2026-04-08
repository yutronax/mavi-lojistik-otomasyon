
import sys
import os
import json

# Add current directory to path
sys.path.insert(0, os.getcwd())

from tools.submit_approved_loads import YukBuradaSubmitter

def test_normalization():
    print("--- Testing Phone Normalization ---")
    submitter = YukBuradaSubmitter()
    test_cases = [
        "05318407744",
        "5318407744",
        "905318407744",
        "+90 531 840 77 44"
    ]
    
    for tc in test_cases:
        variants = submitter.normalize_phone_variants(tc)
        print(f"Input: {tc} -> Variants: {variants}")

def simulate_merger():
    print("\n--- Simulating Merger Selection Logic ---")
    submitter = YukBuradaSubmitter()
    
    # Mock data that looks like found_accounts
    variants = ["05318407744", "5318407744", "905318407744"]
    mock_accounts = [
        {"phone": "905318407744", "user_id": "id90", "fullName": "905318407744"},
        {"phone": "5318407744", "user_id": "id5", "fullName": "yusuf çınar"},
        {"phone": "05318407744", "user_id": "id0", "fullName": "05318407744"}
    ]
    
    # We use the same sorting logic as in the class
    import re
    def is_real_name(name):
        if not name: return False
        return not re.match(r'^[\d\s\-\+]+$', str(name).strip())

    mock_accounts.sort(key=lambda x: (not is_real_name(x['fullName']), variants.index(x['phone'])))
    
    print("Simulation result (Selected first):")
    for i, acc in enumerate(mock_accounts):
        status = "PRIORITIZED" if i == 0 else "REDUNDANT (To be deleted)"
        print(f"{i+1}. Phone: {acc['phone']}, Name: {acc['fullName']} -> {status}")

def live_check():
    print("\n--- Live Check of Master Account ---")
    submitter = YukBuradaSubmitter()
    # This will trigger the get_or_create_user_with_merge internally during __init__
    # or we can call it explicitly
    res = submitter.get_or_create_user_with_merge("05318407744")
    if res:
        print(f"Live Status: Account is healthy.")
        print(f"Active Phone: {res.get('phone')}")
        print(f"Active ID: {res.get('user_id')}")
        print(f"Active Name: {res.get('fullName')}")
    else:
        print("Live Status: Failed to retrieve or merge account.")

if __name__ == "__main__":
    test_normalization()
    simulate_merger()
    live_check()
