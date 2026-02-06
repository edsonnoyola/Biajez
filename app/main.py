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
    """Add missing columns to database - PostgreSQL and SQLite compatible"""
    from sqlalchemy import text, inspect

    # Detect database type
    db_url = os.getenv("DATABASE_URL", "")
    is_postgres = "postgresql" in db_url or "postgres" in db_url

    def column_exists(conn, table, column):
        """Check if column exists in table"""
        try:
            if is_postgres:
                result = conn.execute(text(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = '{column}'"
                ))
                return result.fetchone() is not None
            else:
                result = conn.execute(text(f"PRAGMA table_info({table})"))
                columns = [row[1] for row in result.fetchall()]
                return column in columns
        except:
            return False

    def table_exists(conn, table):
        """Check if table exists"""
        try:
            if is_postgres:
                result = conn.execute(text(
                    f"SELECT table_name FROM information_schema.tables WHERE table_name = '{table}'"
                ))
                return result.fetchone() is not None
            else:
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

            # Create price_alerts table
            if not table_exists(conn, 'price_alerts'):
                if is_postgres:
                    conn.execute(text("""
                        CREATE TABLE price_alerts (
                            id SERIAL PRIMARY KEY,
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
                            is_active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            last_checked_at TIMESTAMP,
                            notified_at TIMESTAMP,
                            notification_count INTEGER DEFAULT 0,
                            extra_data TEXT
                        )
                    """))
                else:
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

            # Create loyalty_programs table
            if not table_exists(conn, 'loyalty_programs'):
                if is_postgres:
                    conn.execute(text("""
                        CREATE TABLE loyalty_programs (
                            id SERIAL PRIMARY KEY,
                            user_id VARCHAR,
                            airline_code VARCHAR,
                            program_name VARCHAR,
                            member_number VARCHAR,
                            tier_status VARCHAR,
                            extra_data TEXT
                        )
                    """))
                else:
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


@app.get("/ticket/{pnr}")
def get_ticket(pnr: str):
    """Serve ticket HTML by PNR"""
    from fastapi.responses import HTMLResponse
    from app.services.ticket_generator import TICKET_STORE

    if pnr in TICKET_STORE:
        return HTMLResponse(content=TICKET_STORE[pnr], status_code=200)

    # If not in memory, return a simple "not found" page
    return HTMLResponse(
        content=f"""
        <html>
        <head><title>Ticket Not Found</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px;">
            <h1>Ticket no encontrado</h1>
            <p>El ticket con PNR <strong>{pnr}</strong> no está disponible.</p>
            <p>Los tickets se generan al momento de la compra y están disponibles por tiempo limitado.</p>
        </body>
        </html>
        """,
        status_code=404
    )


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

    # Check database
    db_url = os.getenv("DATABASE_URL", "not_set")
    db_type = "postgresql" if "postgresql" in db_url else "sqlite" if "sqlite" in db_url else "unknown"

    return {
        "status": "healthy",
        "python": platform.python_version(),
        "system": platform.system(),
        "duffel_configured": bool(os.getenv("DUFFEL_ACCESS_TOKEN")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "whatsapp_configured": bool(os.getenv("WHATSAPP_ACCESS_TOKEN")),
        "redis_configured": bool(os.getenv("REDIS_URL")),
        "database_type": db_type,
        "database_configured": db_url != "not_set",
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


@app.post("/admin/fix-db")
def admin_fix_db(secret: str):
    """Manually add missing columns to PostgreSQL database"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from sqlalchemy import text
    results = []

    try:
        with engine.connect() as conn:
            # Add registration_step to profiles
            try:
                conn.execute(text("ALTER TABLE profiles ADD COLUMN registration_step VARCHAR"))
                conn.commit()
                results.append("Added profiles.registration_step")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    results.append("profiles.registration_step already exists")
                else:
                    results.append(f"profiles.registration_step error: {e}")

            # Add extra_data to notifications
            try:
                conn.execute(text("ALTER TABLE notifications ADD COLUMN extra_data TEXT"))
                conn.commit()
                results.append("Added notifications.extra_data")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                    results.append("notifications.extra_data already exists")
                else:
                    results.append(f"notifications.extra_data error: {e}")

            # Add columns to trips
            for col in ['baggage_services', 'checkin_status', 'boarding_pass_url', 'duffel_order_id']:
                try:
                    col_type = "VARCHAR DEFAULT 'NOT_CHECKED_IN'" if col == 'checkin_status' else "VARCHAR" if col != 'baggage_services' else "TEXT"
                    conn.execute(text(f"ALTER TABLE trips ADD COLUMN {col} {col_type}"))
                    conn.commit()
                    results.append(f"Added trips.{col}")
                except Exception as e:
                    if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                        results.append(f"trips.{col} already exists")
                    else:
                        results.append(f"trips.{col} error: {e}")

        return {"status": "ok", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e), "partial_results": results}


@app.post("/admin/fix-profile-phone")
def admin_fix_profile_phone(secret: str, user_id: str, new_phone: str):
    """Fix phone number in profile"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.db.database import SessionLocal
    from app.models.models import Profile

    try:
        db = SessionLocal()
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            db.close()
            return {"status": "not_found", "user_id": user_id}

        old_phone = profile.phone_number
        profile.phone_number = new_phone
        db.commit()
        db.close()
        return {"status": "ok", "old_phone": old_phone, "new_phone": new_phone}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/admin/profile-by-userid/{user_id}")
def admin_get_profile_by_userid(user_id: str, secret: str):
    """Get profile by user_id"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.db.database import SessionLocal
    from app.models.models import Profile

    try:
        db = SessionLocal()
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            db.close()
            return {"status": "not_found", "user_id": user_id}

        result = {
            "status": "found",
            "profile": {
                "user_id": profile.user_id,
                "legal_first_name": profile.legal_first_name,
                "legal_last_name": profile.legal_last_name,
                "email": profile.email,
                "phone_number": profile.phone_number,
                "dob": str(profile.dob) if profile.dob else None,
                "gender": str(profile.gender) if profile.gender else None,
                "passport_number": profile.passport_number,
                "passport_country": profile.passport_country,
                "passport_expiry": str(profile.passport_expiry) if profile.passport_expiry else None,
                "registration_step": profile.registration_step,
            }
        }
        db.close()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/admin/profile/{phone}")
def admin_get_profile(phone: str, secret: str):
    """Get profile by phone number"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.db.database import SessionLocal
    from app.models.models import Profile

    try:
        db = SessionLocal()
        # Try different phone formats
        profile = db.query(Profile).filter(
            (Profile.phone_number == phone) |
            (Profile.phone_number == f"52{phone}") |
            (Profile.phone_number.contains(phone))
        ).first()

        if not profile:
            db.close()
            return {"status": "not_found", "phone": phone}

        result = {
            "status": "found",
            "profile": {
                "user_id": profile.user_id,
                "legal_first_name": profile.legal_first_name,
                "legal_last_name": profile.legal_last_name,
                "email": profile.email,
                "phone_number": profile.phone_number,
                "dob": str(profile.dob) if profile.dob else None,
                "gender": str(profile.gender) if profile.gender else None,
                "passport_country": profile.passport_country,
                "registration_step": profile.registration_step
            }
        }
        db.close()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/admin/profiles")
def admin_list_profiles(secret: str):
    """List all profiles"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.db.database import SessionLocal
    from app.models.models import Profile

    try:
        db = SessionLocal()
        profiles = db.query(Profile).all()
        result = {
            "status": "ok",
            "count": len(profiles),
            "profiles": [
                {
                    "user_id": p.user_id,
                    "name": f"{p.legal_first_name or ''} {p.legal_last_name or ''}".strip(),
                    "phone": p.phone_number,
                    "email": p.email,
                    "registration_step": p.registration_step
                }
                for p in profiles
            ]
        }
        db.close()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}
