"""
Encryption utilities for PII data (passport numbers, etc.)
Uses Fernet symmetric encryption with a key from environment variable.
"""
import os
from cryptography.fernet import Fernet

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        key = os.getenv("ENCRYPTION_KEY")
        if not key:
            print("⚠️ ENCRYPTION_KEY not set - passport data will NOT be encrypted")
            return None
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(plain_text: str) -> str:
    """Encrypt a string value. Returns encrypted string or original if no key."""
    if not plain_text or plain_text in ["", "N/A", "000000000"]:
        return plain_text
    f = _get_fernet()
    if f is None:
        return plain_text
    try:
        return f.encrypt(plain_text.encode()).decode()
    except Exception as e:
        print(f"⚠️ Encryption failed: {e}")
        return plain_text


def decrypt_value(encrypted_text: str) -> str:
    """Decrypt a string value. Returns decrypted string or original if not encrypted."""
    if not encrypted_text or encrypted_text in ["", "N/A", "000000000"]:
        return encrypted_text
    f = _get_fernet()
    if f is None:
        return encrypted_text
    try:
        return f.decrypt(encrypted_text.encode()).decode()
    except Exception:
        # Not encrypted (legacy data) - return as-is
        return encrypted_text


def generate_key() -> str:
    """Generate a new Fernet encryption key. Run once and save to ENCRYPTION_KEY env var."""
    return Fernet.generate_key().decode()
