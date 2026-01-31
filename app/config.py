"""
Configuration and Environment Validation
"""
import os
from dotenv import load_dotenv
from typing import List, Optional

# Load environment variables
load_dotenv()

class ConfigError(Exception):
    """Raised when configuration is invalid"""
    pass

# Required environment variables
REQUIRED_VARS = [
    "DUFFEL_ACCESS_TOKEN",
]

# Optional but recommended variables
RECOMMENDED_VARS = [
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "DUFFEL_WEBHOOK_SECRET",
]

def validate_environment() -> tuple[bool, List[str], List[str]]:
    """
    Validate that all required environment variables are set
    
    Returns:
        Tuple of (is_valid, missing_required, missing_recommended)
    """
    missing_required = []
    missing_recommended = []
    
    # Check required variables
    for var in REQUIRED_VARS:
        if not os.getenv(var):
            missing_required.append(var)
    
    # Check recommended variables
    for var in RECOMMENDED_VARS:
        if not os.getenv(var):
            missing_recommended.append(var)
    
    is_valid = len(missing_required) == 0
    
    return is_valid, missing_required, missing_recommended

def get_config_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """
    Get configuration value with optional default
    """
    return os.getenv(key, default)

def is_production() -> bool:
    """
    Check if running in production mode
    """
    return os.getenv("ENVIRONMENT", "development").lower() == "production"

def is_development() -> bool:
    """
    Check if running in development mode
    """
    return not is_production()

# Configuration values
DUFFEL_TOKEN = get_config_value("DUFFEL_ACCESS_TOKEN")
STRIPE_SECRET_KEY = get_config_value("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = get_config_value("STRIPE_PUBLISHABLE_KEY")
DUFFEL_WEBHOOK_SECRET = get_config_value("DUFFEL_WEBHOOK_SECRET")
DATABASE_URL = get_config_value("DATABASE_URL", "sqlite:///./biajez.db")
ENVIRONMENT = get_config_value("ENVIRONMENT", "development")

# Validate on import
is_valid, missing_required, missing_recommended = validate_environment()

if not is_valid:
    error_msg = f"""
    ❌ CONFIGURATION ERROR ❌
    
    Missing required environment variables:
    {', '.join(missing_required)}
    
    Please create a .env file with these variables.
    See .env.example for reference.
    """
    raise ConfigError(error_msg)

if missing_recommended:
    print(f"""
    ⚠️  WARNING: Missing recommended environment variables:
    {', '.join(missing_recommended)}
    
    The application will run but some features may not work correctly.
    """)

print(f"""
✅ Configuration loaded successfully
Environment: {ENVIRONMENT}
Duffel API: {'✓' if DUFFEL_TOKEN else '✗'}
Stripe API: {'✓' if STRIPE_SECRET_KEY else '✗'}
Webhooks: {'✓' if DUFFEL_WEBHOOK_SECRET else '✗'}
""")
