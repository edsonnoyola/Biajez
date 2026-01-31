import os
from amadeus import Client

def debug_hex(label, s):
    print(f"{label}: '{s}'")
    print(f"Hex: {s.encode('utf-8').hex()}")

def force_check():
    print("--- DEEP DEBUG: Checking for Invisible Characters ---")

    # 1. TEST KEYS
    test_key = "OQzterfPsAWd8wH8swc4nqmZNedvOygF"
    test_secret = "wISAgaAkVzqML0Qh"
    
    debug_hex("Test Key", test_key)
    debug_hex("Test Secret", test_secret)

    print(f"\n1. Testing TEST Keys (Hostname: test)...")
    try:
        amadeus_test = Client(
            client_id=test_key,
            client_secret=test_secret,
            hostname='test'
        )
        amadeus_test.reference_data.urls.checkin_links.get(airlineCode='BA')
        print("✅ TEST Keys are ACTIVE and working!")
    except Exception as e:
        print(f"❌ TEST Keys Failed: {e}")

    # 2. PRODUCTION KEYS
    prod_key = "Bk1XBLE2YNBxpGhgx8vrl0IvrMMZZmOf"
    prod_secret = "GOtsyI8Pt3d8cjAJ"
    
    debug_hex("Prod Key", prod_key)
    debug_hex("Prod Secret", prod_secret)

    print(f"\n2. Testing PRODUCTION Keys (Hostname: production)...")
    try:
        amadeus_prod = Client(
            client_id=prod_key,
            client_secret=prod_secret,
            hostname='production'
        )
        amadeus_prod.reference_data.urls.checkin_links.get(airlineCode='BA')
        print("✅ PRODUCTION Keys are ACTIVE and working!")
    except Exception as e:
        print(f"❌ PRODUCTION Keys Failed: {e}")

if __name__ == "__main__":
    force_check()
