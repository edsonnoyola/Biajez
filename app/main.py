from dotenv import load_dotenv
load_dotenv() # Load env vars before anything else

import os
# DEBUG: Print env vars status at startup
print("=" * 50)
print("ENVIRONMENT VARIABLES CHECK:")
print(f"   DUFFEL_ACCESS_TOKEN: {'SET' if os.getenv('DUFFEL_ACCESS_TOKEN') else 'NOT SET'}")
print(f"   OPENAI_API_KEY: {'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")
print(f"   WHATSAPP_ACCESS_TOKEN: {'SET' if os.getenv('WHATSAPP_ACCESS_TOKEN') else 'NOT SET'}")
print(f"   REDIS_URL: {'SET' if os.getenv('REDIS_URL') else 'NOT SET'}")
if os.getenv('DUFFEL_ACCESS_TOKEN'):
    token = os.getenv('DUFFEL_ACCESS_TOKEN')
    print(f"   DUFFEL token preview: {token[:25]}..." if len(token) > 25 else f"   DUFFEL token: {token}")
print("=" * 50)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.models import models
from app.db.database import engine
from app.api import routes
from app.api import webhooks
from app.api import flight_changes
from app.api import hotel_cancellations
from app.api import whatsapp_handler
from app.api import whatsapp_meta

# NEW: Import new API routers
from app.api import baggage
from app.api import itinerary
from app.api import visa
from app.api import checkin

# NEW: Import scheduler service
from app.services.scheduler_service import scheduler_service

# Create tables
models.Base.metadata.create_all(bind=engine)

# Run migrations for new columns (safe to run multiple times)
def run_migrations():
    """Add missing columns to database"""
    from sqlalchemy import text
    migrations = [
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS baggage_services TEXT;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS checkin_status VARCHAR DEFAULT 'NOT_CHECKED_IN';",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS boarding_pass_url VARCHAR;",
        "ALTER TABLE trips ADD COLUMN IF NOT EXISTS duffel_order_id VARCHAR;",
        "ALTER TABLE notifications ADD COLUMN IF NOT EXISTS extra_data TEXT;",
    ]
    try:
        with engine.connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(text(sql))
                    conn.commit()
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        print(f"Migration warning: {e}")
        print("✅ Database migrations complete")
    except Exception as e:
        print(f"⚠️ Migration skipped: {e}")

run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup/shutdown events
    """
    # Startup
    print("Starting Antigravity API...")

    # Start the background scheduler
    try:
        scheduler_service.start()
        print("Background scheduler started")
    except Exception as e:
        print(f"Warning: Could not start scheduler: {e}")

    yield

    # Shutdown
    print("Shutting down Antigravity API...")
    try:
        scheduler_service.shutdown()
        print("Background scheduler stopped")
    except Exception as e:
        print(f"Warning: Error stopping scheduler: {e}")


app = FastAPI(
    title="Antigravity API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]  # Expose all headers
)

# Core routers
app.include_router(webhooks.router)
app.include_router(flight_changes.router)
app.include_router(hotel_cancellations.router)
app.include_router(whatsapp_meta.router)     # Meta Direct (priority)
# app.include_router(whatsapp_handler.router)  # Twilio (disabled - conflicts with Meta)
app.include_router(routes.router)

# NEW: Feature routers
app.include_router(baggage.router)
app.include_router(itinerary.router)
app.include_router(visa.router)
app.include_router(checkin.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Antigravity API"}


@app.get("/scheduler/status")
def get_scheduler_status():
    """Get status of all scheduled background jobs"""
    return {
        "jobs": scheduler_service.get_jobs_status()
    }
