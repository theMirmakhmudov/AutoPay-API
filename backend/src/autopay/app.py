import os

import sentry_sdk
import uvicorn
from fastapi import FastAPI

from autopay.api import merchants, payments, webhooks
from autopay.core.config import settings

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
    )
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from autopay.core.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database is now managed via Alembic migrations.
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for parsing and processing automated payments from Telegram.",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Include routers
app.include_router(webhooks.router, prefix=f"{settings.API_V1_STR}/webhooks", tags=["Webhooks"])
app.include_router(payments.router, prefix=f"{settings.API_V1_STR}/payments", tags=["Payments"])
app.include_router(merchants.router, prefix=f"{settings.API_V1_STR}/merchants", tags=["Merchants"])


@app.get("/", include_in_schema=False)
def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "AutoPay API is running."}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
