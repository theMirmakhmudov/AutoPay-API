from fastapi import Security, HTTPException, status, Depends
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session
from core.database import get_db
from core.encryption import hash_api_key
from models.payment import Merchant

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def get_current_merchant(
    api_key: str = Security(api_key_header),
    db: Session = Depends(get_db)
) -> Merchant:
    """
    Validates the API key and returns the authenticated Merchant.
    The raw key is hashed before DB lookup — the plain key never touches the DB.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-API-Key header"
        )

    # Hash the incoming key and look up the hash in the DB
    key_hash = hash_api_key(api_key)
    merchant = db.query(Merchant).filter(Merchant.api_key_hash == key_hash).first()

    if not merchant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )
    return merchant
