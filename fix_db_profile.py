import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
os.environ["DATABASE_URL"] = "sqlite:///./antigravity.db"

from app.db.database import SessionLocal
from app.models.models import Profile

def fix_profile():
    print("--- Fixing Demo User Profile ---")
    db = SessionLocal()
    try:
        user_id = "demo-user"
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        
        if profile:
            print(f"Found profile: {profile.legal_first_name} {profile.legal_last_name}, Phone: {profile.phone_number}")
            
            # Update to valid data
            profile.legal_first_name = "Juan"
            profile.legal_last_name = "Pérez"
            profile.email = "juan.perez@example.com"
            profile.phone_number = "+16505550100" # Valid E.164
            profile.passport_number = "A98765432"
            profile.passport_country = "MX"
            profile.dob = datetime.strptime("1985-06-15", "%Y-%m-%d").date()
            profile.passport_expiry = datetime.strptime("2032-06-15", "%Y-%m-%d").date()
            
            db.commit()
            print("✅ Profile updated successfully to Juan Pérez with valid phone!")
        else:
            print("❌ Profile not found. Creating new one...")
            profile = Profile(
                user_id=user_id,
                legal_first_name="Juan",
                legal_last_name="Pérez",
                email="juan.perez@example.com",
                phone_number="+16505550100",
                gender="M",
                dob=datetime.strptime("1985-06-15", "%Y-%m-%d").date(),
                passport_number="A98765432",
                passport_expiry=datetime.strptime("2032-06-15", "%Y-%m-%d").date(),
                passport_country="MX"
            )
            db.add(profile)
            db.commit()
            print("✅ New profile created.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    fix_profile()
