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
from app.api import loyalty
from app.api import ancillary
from app.api import hold_orders
from app.api import price_alerts

# NEW: Import scheduler service
from app.services.scheduler_service import scheduler_service

# Create tables
models.Base.metadata.create_all(bind=engine)

# Run migrations for new columns (safe to run multiple times)
def run_migrations():
    """Add missing columns to database - SQLite compatible"""
    from sqlalchemy import text, inspect

    def column_exists(conn, table, column):
        """Check if column exists in table (SQLite compatible)"""
        try:
            result = conn.execute(text(f"PRAGMA table_info({table})"))
            columns = [row[1] for row in result.fetchall()]
            return column in columns
        except:
            return False

    def table_exists(conn, table):
        """Check if table exists (SQLite compatible)"""
        try:
            result = conn.execute(text(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"
            ))
            return result.fetchone() is not None
        except:
            return False

    try:
        with engine.connect() as conn:
            # Add columns to trips table
            if not column_exists(conn, 'trips', 'baggage_services'):
                conn.execute(text("ALTER TABLE trips ADD COLUMN baggage_services TEXT"))
                conn.commit()
            if not column_exists(conn, 'trips', 'checkin_status'):
                conn.execute(text("ALTER TABLE trips ADD COLUMN checkin_status VARCHAR DEFAULT 'NOT_CHECKED_IN'"))
                conn.commit()
            if not column_exists(conn, 'trips', 'boarding_pass_url'):
                conn.execute(text("ALTER TABLE trips ADD COLUMN boarding_pass_url VARCHAR"))
                conn.commit()
            if not column_exists(conn, 'trips', 'duffel_order_id'):
                conn.execute(text("ALTER TABLE trips ADD COLUMN duffel_order_id VARCHAR"))
                conn.commit()

            # Add column to notifications table
            if not column_exists(conn, 'notifications', 'extra_data'):
                conn.execute(text("ALTER TABLE notifications ADD COLUMN extra_data TEXT"))
                conn.commit()

            # Create price_alerts table (SQLite compatible)
            if not table_exists(conn, 'price_alerts'):
                conn.execute(text("""
                    CREATE TABLE price_alerts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR,
                        phone_number VARCHAR,
                        search_type VARCHAR,
                        origin VARCHAR,
                        destination VARCHAR,
                        departure_date VARCHAR,
                        return_date VARCHAR,
                        target_price FLOAT,
                        initial_price FLOAT,
                        lowest_price FLOAT,
                        current_price FLOAT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_checked_at TIMESTAMP,
                        notified_at TIMESTAMP,
                        notification_count INTEGER DEFAULT 0,
                        extra_data TEXT
                    )
                """))
                conn.commit()
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_price_alerts_user ON price_alerts(user_id)"))
                conn.commit()

            # Create loyalty_programs table (SQLite compatible)
            if not table_exists(conn, 'loyalty_programs'):
                conn.execute(text("""
                    CREATE TABLE loyalty_programs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id VARCHAR,
                        airline_code VARCHAR,
                        program_name VARCHAR,
                        member_number VARCHAR,
                        tier_status VARCHAR,
                        extra_data TEXT
                    )
                """))
                conn.commit()
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_loyalty_user ON loyalty_programs(user_id)"))
                conn.commit()

            # Add registration_step to profiles table
            if not column_exists(conn, 'profiles', 'registration_step'):
                conn.execute(text("ALTER TABLE profiles ADD COLUMN registration_step VARCHAR"))
                conn.commit()

            print("✅ Database migrations complete")
    except Exception as e:
        print(f"⚠️ Migration error: {e}")

run_migrations()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup/shutdown events
    """
    # Startup
    print("Starting Biatriz API...")

    # Start the background scheduler
    try:
        scheduler_service.start()
        print("Background scheduler started")
    except Exception as e:
        print(f"Warning: Could not start scheduler: {e}")

    yield

    # Shutdown
    print("Shutting down Biatriz API...")
    try:
        scheduler_service.shutdown()
        print("Background scheduler stopped")
    except Exception as e:
        print(f"Warning: Error stopping scheduler: {e}")


app = FastAPI(
    title="Biatriz API",
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
app.include_router(loyalty.router)
app.include_router(ancillary.router)
app.include_router(hold_orders.router)
app.include_router(price_alerts.router)


@app.get("/")
def read_root():
    return {"message": "Welcome to Biatriz API"}


@app.get("/health")
def health_check():
    """Health check endpoint for keep-alive pings"""
    return {"status": "ok", "service": "biajez"}


@app.get("/scheduler/status")
def get_scheduler_status():
    """Get status of all scheduled background jobs"""
    return {
        "jobs": scheduler_service.get_jobs_status()
    }


# ============================================
# ADMIN ENDPOINTS (Protected)
# ============================================
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "biajez_admin_2026")

@app.post("/admin/restart")
def admin_restart(secret: str):
    """
    Restart the server (Render will auto-restart on exit).
    Usage: curl -X POST "https://biajez.onrender.com/admin/restart?secret=YOUR_SECRET"
    """
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    import sys
    import threading

    def delayed_exit():
        import time
        time.sleep(1)
        print("🔄 Admin restart requested - Exiting process...")
        sys.exit(0)

    # Exit in background so we can return response first
    threading.Thread(target=delayed_exit, daemon=True).start()

    return {"status": "ok", "message": "Server will restart in 1 second"}


@app.get("/admin/health")
def admin_health():
    """Health check with system info"""
    import platform
    return {
        "status": "healthy",
        "python": platform.python_version(),
        "system": platform.system(),
        "duffel_configured": bool(os.getenv("DUFFEL_ACCESS_TOKEN")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "whatsapp_configured": bool(os.getenv("WHATSAPP_ACCESS_TOKEN")),
        "redis_configured": bool(os.getenv("REDIS_URL")),
    }


@app.get("/admin/logs")
def admin_logs(secret: str, lines: int = 50):
    """Get recent application logs (if available)"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    # Return scheduler job status as proxy for logs
    return {
        "scheduler_jobs": scheduler_service.get_jobs_status(),
        "message": "Full logs available in Render Dashboard"
    }


@app.get("/admin/profile/{phone}")
def admin_get_profile(phone: str, secret: str):
    """Get profile by phone number"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.db.database import SessionLocal
    from app.models.models import Profile

    db = SessionLocal()
    try:
        # Try different phone formats
        profile = db.query(Profile).filter(
            (Profile.phone_number == phone) |
            (Profile.phone_number == f"52{phone}") |
            (Profile.phone_number.contains(phone))
        ).first()

        if not profile:
            return {"status": "not_found", "phone": phone}

        return {
            "status": "found",
            "profile": {
                "user_id": profile.user_id,
                "legal_first_name": profile.legal_first_name,
                "legal_last_name": profile.legal_last_name,
                "email": profile.email,
                "phone_number": profile.phone_number,
                "dob": str(profile.dob) if profile.dob else None,
                "gender": profile.gender.value if profile.gender else None,
                "passport_number": profile.passport_number[-4:] if profile.passport_number and len(profile.passport_number) > 4 else profile.passport_number,
                "passport_country": profile.passport_country,
                "passport_expiry": str(profile.passport_expiry) if profile.passport_expiry else None,
                "registration_step": profile.registration_step
            }
        }
    finally:
        db.close()


@app.get("/admin/profiles")
def admin_list_profiles(secret: str):
    """List all profiles"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.db.database import SessionLocal
    from app.models.models import Profile

    db = SessionLocal()
    try:
        profiles = db.query(Profile).all()
        return {
            "status": "ok",
            "count": len(profiles),
            "profiles": [
                {
                    "user_id": p.user_id,
                    "name": f"{p.legal_first_name} {p.legal_last_name}",
                    "phone": p.phone_number,
                    "email": p.email,
                    "registration_step": p.registration_step
                }
                for p in profiles
            ]
        }
    finally:
        db.close()
