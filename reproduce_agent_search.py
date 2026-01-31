import asyncio
import os
from app.ai.agent import AntigravityAgent
from datetime import datetime

# Force env vars
from dotenv import load_dotenv
load_dotenv()

async def test_agent():
    print("Initializing Agent...")
    agent = AntigravityAgent()
    
    user_input = "Vuelo de Mexico a Madrid"
    print(f"User Input: {user_input}")
    
    messages = [{"role": "user", "content": user_input}]
    user_context = "User is in testing mode."
    
    print("Sending to Agent...")
    response = await agent.chat(messages, user_context)
    
    if response.tool_calls:
        for tool_call in response.tool_calls:
            print(f"Tool Call: {tool_call.function.name}")
            print(f"Arguments: {tool_call.function.arguments}")
            
            # If it's search, let's try to run it with those args
            if tool_call.function.name == "search_hybrid_flights":
                import json
                args = json.loads(tool_call.function.arguments)
                
                from app.services.flight_engine import FlightAggregator
                aggregator = FlightAggregator()
                
                print(f"Executing Search with Agent Args: {args}")
                results = await aggregator.search_hybrid_flights(
                    origin=args["origin"],
                    destination=args["destination"],
                    departure_date=args["date"],
                    cabin_class=args.get("cabin", "ECONOMY")
                )
                print(f"Results Found: {len(results)}")
                if len(results) == 0:
                    print("CRITICAL: Agent args returned 0 flights.")
                else:
                    print("SUCCESS: Agent args returned flights.")
    else:
        print("Agent did not call any tools.")
        print(f"Response: {response.content}")

if __name__ == "__main__":
    asyncio.run(test_agent())
