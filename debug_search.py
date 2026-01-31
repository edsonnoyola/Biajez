import asyncio
import os
from app.services.flight_engine import FlightAggregator
from datetime import datetime, timedelta

# Force env vars if needed, or rely on load_dotenv
from dotenv import load_dotenv
load_dotenv()

async def test_search():
    print(f"DEBUG: USE_MOCK_DATA = {os.getenv('USE_MOCK_DATA')}")
    
    aggregator = FlightAggregator()
    date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"Searching LHR -> JFK for {date}...")
    results = await aggregator.search_hybrid_flights(
        origin="LHR",
        destination="JFK",
        departure_date=date,
        cabin_class="ECONOMY"
    )
    
    print(f"Found {len(results)} flights.")
    for f in results:
        print(f"- {f.provider} | {f.price} {f.currency} | {f.offer_id}")

if __name__ == "__main__":
    asyncio.run(test_search())
