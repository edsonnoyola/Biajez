import os
import redis
import json

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
print(f"Connecting to {redis_url}")

r = redis.from_url(redis_url, decode_responses=True)
phone = "525610016226"
key = f"whatsapp:session:{phone}"
history_key = f"whatsapp:history:{phone}"

# Check what's there
print(f"Checking session for {phone}...")
session_data = r.get(key)
if session_data:
    print("Found session data. Clearing...")
    r.delete(key)
    print("✅ Session cleared.")
else:
    print("No session data found.")

# Also clear any other potential keys
keys = r.keys(f"*{phone}*")
for k in keys:
    print(f"Deleting related key: {k}")
    r.delete(k)

print("Done.")
