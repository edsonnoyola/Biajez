import requests
import os
from dotenv import load_dotenv

load_dotenv()

def send_test_message(to_number, label):
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    
    print(f"\n--- Testing {label}: {to_number} ---")
    
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": {"code": "en_US"}
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Exception: {e}")
        return False

# Test formats
# The number from the user/webhook is likely: 5215572461012 (Mexico with '1')

# Test send to Admin Number (5215610016226)
# Format 1: With '1' (standard Mexico international for mobile)
send_test_message("5215610016226", "Admin (with 1)")

# Format 2: Without '1'
send_test_message("525610016226", "Admin (no 1)")
