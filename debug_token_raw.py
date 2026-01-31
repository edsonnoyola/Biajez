import requests
import os

def get_token(env_name, hostname, client_id, client_secret):
    print(f"\n--- Testing {env_name} Token ---")
    url = f"https://{hostname}/v1/security/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    print(f"POST {url}")
    print(f"ID: {client_id}")
    # print(f"Secret: {client_secret}") 
    
    try:
        response = requests.post(url, headers=headers, data=data)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ TOKEN ACQUIRED! Keys are valid.")
            return True
        else:
            print("❌ FAILED to get token.")
            return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False

if __name__ == "__main__":
    # Test Keys from Screenshot
    test_id = "OQzterfPsAWd8wH8swc4nqmZNedvOygF"
    test_secret = "wISAgaAkVzqML0Qh"
    get_token("TEST", "test.api.amadeus.com", test_id, test_secret)

    # Prod Keys from Screenshot
    prod_id = "Bk1XBLE2YNBxpGhgx8vrl0IvrMMZZmOf"
    prod_secret = "GOtsyI8Pt3d8cjAJ"
    get_token("PRODUCTION", "api.amadeus.com", prod_id, prod_secret)
