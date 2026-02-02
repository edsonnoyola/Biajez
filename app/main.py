from dotenv import load_dotenv
load_dotenv() # Load env vars before anything else

import os
# DEBUG: Print env vars status at startup
print("=" * 50)
print("🔧 ENVIRONMENT VARIABLES CHECK:")
print(f"   DUFFEL_ACCESS_TOKEN: {'✅ SET' if os.getenv('DUFFEL_ACCESS_TOKEN') else '❌ NOT SET'}")
print(f"   OPENAI_API_KEY: {'✅ SET' if os.getenv('OPENAI_API_KEY') else '❌ NOT SET'}")
print(f"   WHATSAPP_ACCESS_TOKEN: {'✅ SET' if os.getenv('WHATSAPP_ACCESS_TOKEN') else '❌ NOT SET'}")
print(f"   REDIS_URL: {'✅ SET' if os.getenv('REDIS_URL') else '❌ NOT SET'}")
if os.getenv('DUFFEL_ACCESS_TOKEN'):
    token = os.getenv('DUFFEL_ACCESS_TOKEN')
    print(f"   DUFFEL token preview: {token[:25]}..." if len(token) > 25 else f"   DUFFEL token: {token}")
print("=" * 50)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models import models
from app.db.database import engine
from app.api import routes
from app.api import webhooks
from app.api import flight_changes
from app.api import hotel_cancellations
from app.api import whatsapp_handler
from app.api import whatsapp_meta

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Antigravity API", version="1.0.0")

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]  # Expose all headers
)

app.include_router(webhooks.router)
app.include_router(flight_changes.router)
app.include_router(hotel_cancellations.router)
app.include_router(whatsapp_meta.router)     # Meta Direct (priority)
# app.include_router(whatsapp_handler.router)  # Twilio (disabled - conflicts with Meta)
app.include_router(routes.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Antigravity API"}
