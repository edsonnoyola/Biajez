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
from app.api import order_endpoints

# NEW: Import scheduler service
from app.services.scheduler_service import scheduler_service

# Create tables (with retry for transient DB connection issues)
for _attempt in range(3):
    try:
        models.Base.metadata.create_all(bind=engine)
        break
    except Exception as _db_err:
        print(f"⚠️ DB create_all attempt {_attempt+1} failed: {_db_err}")
        if _attempt < 2:
            import time
            time.sleep(5)
        else:
            print("❌ Could not connect to database after 3 attempts - starting anyway")

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

try:
    run_migrations()
except Exception as _mig_err:
    print(f"⚠️ Migrations failed (non-fatal): {_mig_err}")


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
app.include_router(order_endpoints.router)


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
ADMIN_SECRET = os.getenv("ADMIN_SECRET")
if not ADMIN_SECRET:
    print("⚠️ WARNING: ADMIN_SECRET not set - admin endpoints will be disabled")

@app.get("/admin/last-confirm/{phone}")
def admin_last_confirm(phone: str, secret: str):
    """Get debug info from the last confirmation attempt for a phone number"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.api.whatsapp_meta import whatsapp_webhook
    if hasattr(whatsapp_webhook, '_last_confirm_debug'):
        info = whatsapp_webhook._last_confirm_debug.get(phone)
        if info:
            return {"status": "ok", "debug": info}
    return {"status": "ok", "debug": None, "message": "No confirmation attempt recorded for this phone"}


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


@app.get("/admin/redis-status")
def admin_redis_status(secret: str):
    """Check Redis connectivity and session data"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.services.whatsapp_redis import session_manager
    import redis

    result = {
        "redis_url_set": bool(os.getenv("REDIS_URL")),
        "session_manager_enabled": session_manager.enabled,
        "fallback_sessions": len(session_manager.fallback_storage),
        "redis_ping": None,
        "test_set_get": None,
    }

    # Test Redis connection
    if session_manager.enabled:
        try:
            session_manager.redis_client.ping()
            result["redis_ping"] = "OK"
        except Exception as e:
            result["redis_ping"] = f"FAILED: {e}"

        # Test set/get
        try:
            session_manager.redis_client.setex("test_key", 10, "test_value")
            val = session_manager.redis_client.get("test_key")
            result["test_set_get"] = "OK" if val == "test_value" else f"MISMATCH: {val}"
        except Exception as e:
            result["test_set_get"] = f"FAILED: {e}"

    return result


@app.get("/admin/session/{phone}")
def admin_get_session(phone: str, secret: str):
    """View a user's session data"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from app.services.whatsapp_redis import session_manager

    session = session_manager.get_session(phone)
    return {
        "phone": phone,
        "redis_enabled": session_manager.enabled,
        "session": {
            "user_id": session.get("user_id"),
            "pending_flights": len(session.get("pending_flights", [])),
            "pending_hotels": len(session.get("pending_hotels", [])),
            "selected_flight": bool(session.get("selected_flight")),
            "selected_hotel": bool(session.get("selected_hotel")),
            "pending_change": session.get("pending_change"),
            "pending_change_offers": bool(session.get("pending_change_offers")),
            "last_updated": session.get("last_updated"),
            "messages_count": len(session.get("messages", [])),
        }
    }


@app.get("/admin/test-confirm/{phone}")
def admin_test_confirm(phone: str, secret: str):
    """Simulate the FULL webhook flow for confirmation - including session init"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from sqlalchemy import text
    from app.services.whatsapp_redis import session_manager
    from app.api.whatsapp_meta import normalize_mx_number

    results = {}

    # Step 1: Load session (same as webhook line 269)
    session = session_manager.get_session(phone)
    results["step1_raw_session"] = {
        "user_id": session.get("user_id"),
        "selected_flight": bool(session.get("selected_flight")),
        "pending_flights": len(session.get("pending_flights", [])),
    }

    # Step 2: Session init - same as webhook lines 275-325
    user_id = session.get("user_id")
    if not user_id:
        normalized_phone = normalize_mx_number(phone)
        phone_variations = [phone, normalized_phone, f"whatsapp_{phone}", f"whatsapp_{normalized_phone}"]
        with engine.connect() as conn:
            for phone_var in phone_variations:
                result = conn.execute(text("SELECT user_id FROM profiles WHERE phone_number = :phone LIMIT 1"), {"phone": phone_var})
                row = result.fetchone()
                if row:
                    user_id = row[0]
                    results["step2_session_init"] = {"method": "phone_number", "matched": phone_var, "user_id": user_id}
                    break
            if not user_id:
                for phone_var in phone_variations:
                    result = conn.execute(text("SELECT user_id FROM profiles WHERE user_id = :uid LIMIT 1"), {"uid": phone_var})
                    row = result.fetchone()
                    if row:
                        user_id = row[0]
                        results["step2_session_init"] = {"method": "user_id", "matched": phone_var, "user_id": user_id}
                        break
        if not user_id:
            user_id = f"whatsapp_{phone}"
            results["step2_session_init"] = {"method": "new_user", "user_id": user_id}
        session["user_id"] = user_id
    else:
        results["step2_session_init"] = {"method": "already_set", "user_id": user_id}

    # Step 3: Registration check - same as webhook (now raw SQL)
    user_in_registration = False
    with engine.connect() as conn:
        _reg_result = conn.execute(text("SELECT registration_step FROM profiles WHERE user_id = :uid"), {"uid": user_id})
        _reg_row = _reg_result.fetchone()
        if _reg_row and _reg_row[0]:
            user_in_registration = True
    results["step3_registration_check"] = {"in_registration": user_in_registration, "reg_step": str(_reg_row[0]) if _reg_row else None}

    # Step 4: Profile lookup - same as confirmation handler (3 methods)
    row = None
    profile_complete = False
    with engine.connect() as conn:
        # Method 1: user_id
        if user_id:
            result = conn.execute(text("SELECT user_id, legal_first_name, legal_last_name, email, dob FROM profiles WHERE user_id = :uid"), {"uid": user_id})
            row = result.fetchone()
            results["step4_method1_userid"] = {"found": row is not None}

        # Method 2: phone variations
        if not row:
            normalized = normalize_mx_number(phone)
            for phone_var in [phone, normalized, f"whatsapp_{phone}", f"whatsapp_{normalized}"]:
                result = conn.execute(text("SELECT user_id, legal_first_name, legal_last_name, email, dob FROM profiles WHERE phone_number = :phone OR user_id = :uid LIMIT 1"), {"phone": phone_var, "uid": phone_var})
                row = result.fetchone()
                if row:
                    results["step4_method2_phone"] = {"found": True, "matched": phone_var}
                    break
            if not row:
                results["step4_method2_phone"] = {"found": False}

        # Method 3: LIKE pattern
        if not row:
            result = conn.execute(text("SELECT user_id, legal_first_name, legal_last_name, email, dob FROM profiles WHERE phone_number LIKE :p OR user_id LIKE :u LIMIT 1"), {"p": f"%{phone[-10:]}%", "u": f"%{phone[-10:]}%"})
            row = result.fetchone()
            results["step4_method3_like"] = {"found": row is not None}

        if row:
            found_user_id, first_name, last_name, email, dob = row
            checks = {
                "first_name_truthy": bool(first_name),
                "first_name_not_whatsapp": first_name != "WhatsApp" if first_name else False,
                "last_name_truthy": bool(last_name),
                "dob_truthy": bool(dob),
                "email_truthy": bool(email),
                "email_no_temp": "@whatsapp.temp" not in str(email) if email else True,
            }
            profile_complete = all(checks.values())
            results["step5_profile"] = {
                "user_id": found_user_id,
                "first_name": str(first_name),
                "last_name": str(last_name),
                "email": str(email),
                "dob": str(dob),
                "checks": checks,
                "profile_complete": profile_complete,
            }
        else:
            results["step5_profile"] = {"error": "NO PROFILE FOUND BY ANY METHOD"}

    results["FINAL_VERDICT"] = "BOOKING WOULD PROCEED" if profile_complete else "WOULD SHOW PERFIL INCOMPLETO"
    return results


@app.post("/admin/update-profile/{phone}")
def admin_update_profile(phone: str, secret: str, first_name: str = None, last_name: str = None, email: str = None, dob: str = None, passport: str = None, passport_country: str = None, passport_expiry: str = None):
    """Force update a profile with correct data"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from sqlalchemy import text
    updates = []
    params = {"phone": phone}
    if first_name: updates.append("legal_first_name = :fn"); params["fn"] = first_name
    if last_name: updates.append("legal_last_name = :ln"); params["ln"] = last_name
    if email: updates.append("email = :em"); params["em"] = email
    if dob: updates.append("dob = :dob"); params["dob"] = dob
    if passport: updates.append("passport_number = :pp"); params["pp"] = passport
    if passport_country: updates.append("passport_country = :pc"); params["pc"] = passport_country
    if passport_expiry: updates.append("passport_expiry = :pe"); params["pe"] = passport_expiry

    if not updates:
        return {"status": "error", "message": "No fields to update"}

    sql = f"UPDATE profiles SET {', '.join(updates)} WHERE phone_number = :phone"
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        conn.commit()
        return {"status": "ok", "rows_updated": result.rowcount, "fields": list(params.keys())}


@app.get("/admin/debug-profile/{phone}")
def admin_debug_profile(phone: str, secret: str):
    """Debug profile with raw SQL to see exact registration_step value"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from sqlalchemy import text

    results = {}

    with engine.connect() as conn:
        # Direct query for registration_step
        result = conn.execute(
            text("SELECT user_id, registration_step, legal_first_name, dob FROM profiles WHERE phone_number = :phone"),
            {"phone": phone}
        )
        row = result.fetchone()
        if row:
            results["by_phone"] = {
                "user_id": row[0],
                "registration_step": row[1],
                "registration_step_type": str(type(row[1])),
                "registration_step_repr": repr(row[1]),
                "legal_first_name": row[2],
                "dob": str(row[3])
            }

        # Also try by user_id
        result = conn.execute(
            text("SELECT user_id, registration_step, legal_first_name FROM profiles WHERE user_id LIKE :pattern"),
            {"pattern": f"%{phone}%"}
        )
        rows = result.fetchall()
        results["by_user_id_pattern"] = [{"user_id": r[0], "registration_step": r[1], "name": r[2]} for r in rows]

        # Count all profiles
        result = conn.execute(text("SELECT COUNT(*) FROM profiles"))
        results["total_profiles"] = result.fetchone()[0]

    return results


@app.post("/admin/clear-registration")
def admin_clear_registration(secret: str):
    """Force clear registration_step for ALL profiles"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from sqlalchemy import text
    with engine.connect() as conn:
        result = conn.execute(text("UPDATE profiles SET registration_step = NULL WHERE registration_step IS NOT NULL"))
        conn.commit()
        return {"status": "ok", "rows_cleared": result.rowcount}


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


@app.post("/admin/update-profile")
def admin_update_profile(secret: str, user_id: str, first_name: str = None, last_name: str = None,
                          email: str = None, passport: str = None, passport_country: str = None):
    """Directly update profile with raw SQL"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}

    from sqlalchemy import text

    try:
        updates = []
        params = {"user_id": user_id}

        if first_name:
            updates.append("legal_first_name = :first_name")
            params["first_name"] = first_name
        if last_name:
            updates.append("legal_last_name = :last_name")
            params["last_name"] = last_name
        if email:
            updates.append("email = :email")
            params["email"] = email
        if passport:
            updates.append("passport_number = :passport")
            params["passport"] = passport
        if passport_country:
            updates.append("passport_country = :passport_country")
            params["passport_country"] = passport_country

        if not updates:
            return {"status": "error", "message": "No fields to update"}

        sql = f"UPDATE profiles SET {', '.join(updates)} WHERE user_id = :user_id"

        with engine.connect() as conn:
            result = conn.execute(text(sql), params)
            conn.commit()
            return {"status": "ok", "rows_affected": result.rowcount}
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

@app.get("/admin/webhook-log")
def admin_webhook_log(secret: str, n: int = 10):
    """Show last N webhook events from Redis"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}
    import redis, json as _json
    try:
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        logs = r.lrange("webhook_log", 0, n - 1)
        return {"logs": [_json.loads(l) for l in logs]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/booking-errors")
def admin_booking_errors(secret: str, n: int = 10):
    """Show last N booking errors from DB"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT ts, phone, offer_id, provider, amount, error FROM booking_errors ORDER BY id DESC LIMIT :n"),
                {"n": n}
            )
            errors = [dict(row._mapping) for row in result]
            return {"errors": errors}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/list-trips")
def admin_list_trips(secret: str, user_id: str = None):
    """List all trips, optionally filtered by user_id"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            if user_id:
                rows = conn.execute(text("SELECT booking_reference, user_id, status, departure_city, arrival_city, departure_date, total_amount, duffel_order_id, refund_amount FROM trips WHERE user_id = :uid"), {"uid": user_id}).fetchall()
            else:
                rows = conn.execute(text("SELECT booking_reference, user_id, status, departure_city, arrival_city, departure_date, total_amount, duffel_order_id, refund_amount FROM trips")).fetchall()
        return {"trips": [{"booking_ref": r[0], "user_id": r[1], "status": r[2], "origin": r[3], "dest": r[4], "date": str(r[5]), "amount": float(r[6]) if r[6] else 0, "duffel_id": r[7], "refund": float(r[8]) if r[8] else None} for r in rows]}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/admin/delete-trip/{booking_ref}")
def admin_delete_trip(booking_ref: str, secret: str):
    """Delete a trip record by booking_reference"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(text("DELETE FROM trips WHERE booking_reference = :ref"), {"ref": booking_ref})
            conn.commit()
        return {"status": "ok", "deleted": result.rowcount}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/admin/send-test")
def admin_send_test(secret: str, phone: str, msg: str = "Hola, este es un mensaje de prueba del bot Biajez."):
    """Send a test WhatsApp message to verify API connection"""
    if secret != ADMIN_SECRET:
        return {"status": "error", "message": "Invalid secret"}
    import requests as _req
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not phone_number_id or not access_token:
        return {"status": "error", "message": "WhatsApp credentials not configured"}
    # Normalize Mexican numbers
    to_number = phone
    if to_number.startswith("521") and len(to_number) == 13:
        to_number = "52" + to_number[3:]
    url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    data = {"messaging_product": "whatsapp", "to": to_number, "type": "text", "text": {"body": msg}}
    try:
        resp = _req.post(url, json=data, headers=headers)
        return {"status": "ok", "to": to_number, "http_status": resp.status_code, "response": resp.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
