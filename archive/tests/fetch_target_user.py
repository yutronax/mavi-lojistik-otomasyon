
import sys
import os
import json

# Add current directory to path
sys.path.insert(0, os.getcwd())

from tools.submit_approved_loads import YukBuradaSubmitter

def fetch_user(phone):
    submitter = YukBuradaSubmitter()
    
    # Normalize phone
    import re
    clean_phone = re.sub(r'\D', '', str(phone))
    if len(clean_phone) == 10:
        clean_phone = '90' + clean_phone
    elif len(clean_phone) == 11 and clean_phone.startswith('0'):
        clean_phone = '9' + clean_phone
        
    print(f"Fetching data for normalized phone: {clean_phone}")
    
    # Try to login/get user info
    result = submitter.login_user(clean_phone)
    
    if result.get('success'):
        token = result.get('access_token')
        print(f"\nLogin Successful! Token received.")
        print(f"User ID: {result.get('user_id')}")
        
        print("\nFetching full profile...")
        profile = submitter.get_user_info(token)
        if profile.get('success'):
            print("\nFULL USER PROFILE:")
            print(json.dumps(profile.get('user_data'), indent=2, ensure_ascii=False))
        else:
            print(f"\nCould not fetch full profile: {profile.get('error')}")
            # Try alternate endpoint if it exists
            print("Attempting alternate endpoint /api/Users/{id}...")
            alt_url = f"{submitter.api_base_url}/api/Users/{result.get('user_id')}"
            try:
                import requests
                resp = requests.get(alt_url, headers={'Authorization': f'Bearer {token}'})
                if resp.ok:
                    print("\nFULL USER PROFILE (from alt endpoint):")
                    print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
                else:
                    print(f"Alt endpoint failed: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"Request error: {e}")
    else:
        print(f"\nFAILED: {result.get('error')}")
        if result.get('status') == 404:
            print("User does not exist in the system.")

if __name__ == "__main__":
    target_phone = "05309429862"
    fetch_user(target_phone)
