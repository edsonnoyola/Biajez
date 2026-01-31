#!/bin/bash
# Test Amadeus Production Auth directly

CLIENT_ID="8oOTBBDdcpDOY0rPgjt3YSLTIMz0WnAs"
CLIENT_SECRET="m1ESaL0UqVhDljQg"

echo "Testing Authentication against https://api.amadeus.com (Production)..."

curl -v "https://api.amadeus.com/v1/security/oauth2/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=client_credentials&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET"

echo -e "\n\nDone."
