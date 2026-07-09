import hashlib
import secrets
from cryptography.fernet import Fernet
from core.config import settings


# ── Session String Encryption ────────────────────────────────────────────────
# The ENCRYPTION_KEY in .env is a Fernet key. Session strings are encrypted
# before being written to the DB, and decrypted only when Telethon needs them.

def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        raise RuntimeError("ENCRYPTION_KEY is not set in .env")
    return Fernet(key.encode())

def encrypt_session(session_string: str) -> str:
    """Encrypts a plain Telethon StringSession before storing in the DB."""
    return _get_fernet().encrypt(session_string.encode()).decode()

def decrypt_session(encrypted: str) -> str:
    """Decrypts a stored session string back to plain text for Telethon."""
    return _get_fernet().decrypt(encrypted.encode()).decode()


# ── API Key Hashing ──────────────────────────────────────────────────────────
# We NEVER store raw API keys. Only their SHA-256 hash is kept in the DB.
# The merchant sees the key once (in the bot). After that only the hash exists.

def hash_api_key(raw_key: str) -> str:
    """Returns a SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()

def generate_api_key() -> tuple[str, str]:
    """
    Generates a new API key.
    Returns (raw_key, hashed_key).
    raw_key → shown to the merchant once, never stored.
    hashed_key → stored in the DB.
    """
    raw = secrets.token_hex(32)   # 64-char hex string
    return raw, hash_api_key(raw)

def generate_webhook_secret() -> str:
    """Generates a secure secret for signing HMAC-SHA256 webhooks."""
    return secrets.token_hex(32)
