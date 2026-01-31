import requests
import os
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN")
VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
CALLBACK_URL = "https://gemmuliferous-consistent-drake.ngrok-free.dev/v1/whatsapp/webhook"

def configure_webhook():
    if not ACCESS_TOKEN:
        print("❌ No access token found")
        return

    # 1. Get App ID from Token
    print("🔍 Inspecting token...")
    debug_url = f"https://graph.facebook.com/v18.0/debug_token?input_token={ACCESS_TOKEN}&access_token={ACCESS_TOKEN}"
    try:
        res = requests.get(debug_url)
        data = res.json()
        
        if "data" not in data:
            print(f"❌ Error checking token: {data}")
            return
            
        app_id = data["data"]["app_id"]
        print(f"✅ App ID: {app_id}")
        
    except Exception as e:
        print(f"❌ Exception checking token: {e}")
        return

    # 2. Configure Webhook
    print(f"⚙️ Attempting to configure Webhook for App {app_id}...")
    url = f"https://graph.facebook.com/v18.0/{app_id}/subscriptions"
    
    params = {
        "object": "whatsapp_business_account",
        "callback_url": CALLBACK_URL,
        "verify_token": VERIFY_TOKEN,
        "fields": "messages",
        "access_token": ACCESS_TOKEN
    }
    
    try:
        res = requests.post(url, params=params)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")
        
        if res.status_code == 200:
            print("✅ Webhook configured successfully via API!")
        else:
            print("⚠️ API Configuration failed. We likely need the App Dashboard UI.")
            print("Common reasons: Token is not an App Admin token, or lacking permissions.")
            
    except Exception as e:
        print(f"❌ Exception configuring webhook: {e}")

if __name__ == "__main__":
    configure_webhook()
