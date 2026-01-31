#!/usr/bin/env python3
"""
Test to reproduce the 500 error
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("🔍 Probando endpoints para encontrar el error 500...\n")

endpoints = [
    "/v1/search?origin=MEX&destination=CUN&date=2026-01-20&cabin=ECONOMY",
    "/v1/chat",
    "/v1/profile/demo-user",
    "/v1/hotels?location=CUN&check_in=2026-01-20&check_out=2026-01-25",
]

for endpoint in endpoints:
    print(f"Testing: {endpoint}")
    try:
        if "/chat" in endpoint:
            response = requests.post(f"{BASE_URL}{endpoint}", json={
                "user_id": "demo-user",
                "message": "Hello"
            }, timeout=10)
        else:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 500:
            print(f"  ❌ ERROR 500 ENCONTRADO!")
            print(f"  Response: {response.text[:200]}")
        elif response.status_code >= 400:
            print(f"  ⚠️  Error: {response.status_code}")
            print(f"  Response: {response.text[:100]}")
        else:
            print(f"  ✅ OK")
            
    except Exception as e:
        print(f"  ❌ Exception: {str(e)[:100]}")
    
    print()
