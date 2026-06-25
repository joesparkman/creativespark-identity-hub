import requests
import json
import time
import os

# 1. API configuration fetched from environment (Secure)
# These values are now externalized to prevent credential leakage
API_URL = os.environ.get('API_URL')
TOKEN = os.environ.get('AUTH_TOKEN')

# Reusable dynamic identifier context tracking
TEST_USER_ID = f"test_user_{int(time.time())}"

# Simple transparent 1x1 base64 pixel image to bypass upload schema filters
MOCK_IMAGE_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

def run_integration_test():
    if not API_URL or not TOKEN:
        print("❌ Error: API_URL or AUTH_TOKEN not set in environment variables.")
        return

    print("🚀 Firing up CreativeSpark Onboarding Integration Test...")
    
    # =================================================================
    # PHASE 1: VAULT THE GOVERNMENT ID DOCUMENT
    # =================================================================
    id_payload = {
        "action": "UPLOAD_ID",
        "session_token": TOKEN,
        "user_id": TEST_USER_ID,
        "id_image_base64": MOCK_IMAGE_BASE64
    }
    print(f"\n🪪 Sending Government ID payload mapping context for: {TEST_USER_ID}...")
    id_response = requests.post(API_URL, json=id_payload)
    print(f"📊 ID Upload Status Code: {id_response.status_code}")
    
    if id_response.status_code != 200:
        print("❌ ID Document initialization failed. Aborting pipeline test.")
        return

    # =================================================================
    # PHASE 2: VAULT THE PROFILE SELFIE ASSET
    # =================================================================
    selfie_payload = {
        "action": "UPLOAD",
        "session_token": TOKEN,
        "user_id": TEST_USER_ID,
        "selfie_image_base64": MOCK_IMAGE_BASE64
    }
    
    print("\n📸 Sending Selfie asset upload payload context...")
    selfie_response = requests.post(API_URL, json=selfie_payload)
    print(f"📊 Selfie Upload Status Code: {selfie_response.status_code}")
    
    if selfie_response.status_code != 200:
        print("❌ Selfie upload submission failed. Aborting pipeline test.")
        return

    # =================================================================
    # PHASE 3: ASYNC PROCESSING BUFFER
    # =================================================================
    print("\n⏳ Pausing to let async computer vision processing infrastructure resolve...")
    time.sleep(4)
    
    # =================================================================
    # PHASE 4: POLL FOR ALIGNED LEDGER TRANSITIONS
    # =================================================================
    print("\n🔍 Querying backend state engine for verification status metrics...")
    
    status_payload = {
        "action": "STATUS",
        "session_token": TOKEN,
        "user_id": TEST_USER_ID
    }
    
    status_response = requests.post(API_URL, json=status_payload)
    
    print(f"📊 Status Query HTTP Return Code: {status_response.status_code}")
    print("\n🎯 FINAL ONBOARDING BIOMETRIC VERIFICATION STATUS:")
    
    try:
        print(json.dumps(status_response.json(), indent=4))
    except Exception:
        print(f"📥 Raw Fallback Response String: {status_response.text}")

if __name__ == "__main__":
    run_integration_test()