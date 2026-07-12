import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from autopay.app import app
from autopay.core.database import get_db
from autopay.core.encryption import generate_api_key
from autopay.core.security import get_current_merchant
from autopay.models.base import Base
from autopay.models.payment import Merchant

# Use in-memory SQLite for testing to avoid touching Postgres
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function")
def db_session():
    # Create tables
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    # Drop tables after test
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def test_merchant(db_session):
    raw_api_key, api_key_hash = generate_api_key()
    merchant = Merchant(
        id="test_merchant_id",
        name="Test Merchant",
        api_key_hash=api_key_hash,
        is_connected=True
    )
    db_session.add(merchant)
    db_session.commit()
    db_session.refresh(merchant)

    # Attach raw api key for test client usage
    merchant.raw_api_key = raw_api_key
    return merchant

@pytest.fixture(scope="function")
def client(test_merchant):
    # Disable rate limiter for tests
    from autopay.app import limiter
    limiter.enabled = False

    # Override auth to use our test merchant
    app.dependency_overrides[get_current_merchant] = lambda: test_merchant
    with TestClient(app) as c:
        yield c
    # Clean up overrides
    app.dependency_overrides.pop(get_current_merchant, None)
