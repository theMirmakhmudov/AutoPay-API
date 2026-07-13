import pytest
from fastapi import HTTPException

from autopay.core.database import get_db
from autopay.core.encryption import (
    _get_fernet,
    decrypt_session,
    encrypt_session,
    generate_webhook_secret,
)
from autopay.core.security import get_current_merchant


def test_get_db():
    db_gen = get_db()
    db = next(db_gen)
    assert db is not None
    # close the generator
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_encryption_functions(monkeypatch):
    from cryptography.fernet import Fernet
    import autopay.core.config
    monkeypatch.setattr(autopay.core.config.settings, "ENCRYPTION_KEY", Fernet.generate_key().decode())
    
    original = "test_session_string"
    encrypted = encrypt_session(original)
    assert encrypted != original
    decrypted = decrypt_session(encrypted)
    assert decrypted == original

    secret = generate_webhook_secret()
    assert isinstance(secret, str)
    assert len(secret) == 64


def test_encryption_no_key(monkeypatch):
    import autopay.core.config
    monkeypatch.setattr(autopay.core.config.settings, "ENCRYPTION_KEY", "")
    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is not set"):
        _get_fernet()


def test_security_invalid_api_key(db_session):
    with pytest.raises(HTTPException) as exc:
        get_current_merchant(api_key="invalid_key", db=db_session)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Invalid API Key"
