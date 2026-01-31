import os
import asyncio
from amadeus import Client, ResponseError
from duffel_api import Duffel
from dotenv import load_dotenv

load_dotenv()

async def test_amadeus():
    print("\n--- Testing Amadeus ---")
    try:
        # Try full URL for production
        import logging
        logging.basicConfig(level=logging.DEBUG)
        amadeus = Client(
            client_id=os.getenv("AMADEUS_CLIENT_ID"),
            client_secret=os.getenv("AMADEUS_CLIENT_SECRET"),
            hostname="production",
            log_level='debug'
        )
        # Force the base URL if needed (SDK might not allow it easily, but 'production' should work)
        # Let's print the base URL
        # print(f"Amadeus Base URL: {amadeus.client.api_url}") # Hypothetical
        
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode="MAD",
            destinationLocationCode="BCN",
            departureDate="2025-12-16",
            adults=1,
            max=1
        )
        print(f"Amadeus Success! Found {len(response.data)} offers.")
    except ResponseError as error:
        print(f"Amadeus Error: {error}")
        if hasattr(error, 'response'):
            print(f"Body: {error.response.body}")
    except Exception as e:
        print(f"Amadeus Exception: {e}")

async def test_duffel():
    print("\n--- Testing Duffel ---")
    try:
        # Let's try forcing v2 with the new token
        duffel = Duffel(access_token=os.getenv("DUFFEL_ACCESS_TOKEN"), api_version="v2")
        print(f"Initialized Duffel (Version: v2)")
        
        # Use Builder Pattern
        offers = duffel.offer_requests.create() \
            .slices([{
                "origin": "MAD",
                "destination": "BCN",
                "departure_date": "2025-12-16"
            }]) \
            .passengers([{"type": "adult"}]) \
            .cabin_class("economy") \
            .return_offers() \
            .execute()
        print(f"Duffel Success! ID: {offers.id}")
        
    except Exception as e:
        print(f"Duffel Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_amadeus())
    asyncio.run(test_duffel())
