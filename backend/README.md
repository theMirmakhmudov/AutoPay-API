# AvtoPaymentBot

A Telegram-based automated payment detection system designed specifically for the Uzbekistan market. This application uses Telegram Userbots via the Telethon library to intercept incoming transaction notifications from payment systems (Click, Payme, Uzcard, Humo) on behalf of merchants. It acts as an integration middleware, parsing transaction SMS/Messages and automatically firing Webhooks to the merchant's backend server whenever a matching payment intent is fulfilled.

## Table of Contents
- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture & Mechanics](#architecture--mechanics)
- [Setup & Usage](#setup--usage)
- [Environment Variables](#environment-variables)
- [Testing](#testing)
- [License](#license)

## Features
- **Multi-Merchant Support:** Manages concurrent Telegram Userbots for multiple independent merchants dynamically.
- **Smart Payment Parser:** Uses regex to interpret and normalize transaction amounts from Click, Payme, Uzcard, and Humo notification bots.
- **Collision Management:** For multiple identical base amounts, the system temporarily augments subsequent transaction requests by tiny fractions (+0.01 UZS offset/1 tiyin) to maintain uniqueness for idempotent processing.
- **Webhook Integration:** Supports instant asynchronous HTTP webhooks signed with an HMAC (SHA-256) signature payload to alert your backend.
- **Background Health Checking:** A background asynchronous daemon runs every 5 minutes to verify if merchant sessions have been revoked. If an active session is unauthorized, it immediately notifies both the merchant and the system admins via the primary Telegram Management bot.
- **Automated Deployments:** Full support for seamless Docker-compose orchestrations and backend CI/CD routines.

## Technology Stack
- **Python 3.11+**
- **Framework:** FastAPI (Uvicorn)
- **Database:** PostgreSQL (with Asyncpg via SQLAlchemy 2.0 ORM) + Alembic for migrations
- **Telegram APIs:** Telethon (Userbots) and aiogram (Management Bot - *Migrated to Telethon in `bot.py` for simplicity in latest release*)
- **Containerization:** Docker & Docker Compose
- **Error Tracking:** Sentry SDK
- **Testing:** Pytest (with pytest-asyncio)

## Architecture & Mechanics
1. **Management Bot:** Merchants interact with the `@YourManagementBot` on Telegram to generate a `StringSession`.
2. **REST API:** Web applications/services hit the FastAPI endpoints to create a new `PaymentIntent` for a specific merchant. 
3. **Telethon Worker:** `worker/main.py` boots `ClientManager`, executing the management bot and all active merchant userbots inside a unified event loop.
4. **Message Interception:** When a userbot receives a message from `KNOWN_BOT_USERNAMES` (e.g. `@clickuz`), it fires a webhook payload logic check against the database.
5. **Reconciliation:** The `PaymentService` attempts to match the payload amount to an open `PaymentIntent`. If matched, a secure webhook is dispatched.

## Setup & Usage

### 1. Prerequisites
- Docker and Docker Compose installed
- A Telegram API ID and API Hash from `my.telegram.org`
- A Telegram Bot Token from `@BotFather`
- A domain/server pointing to port 80/443 (configured via Nginx proxy).

### 2. Configuration
Create a `.env` file in the `backend/` directory referencing `.env.example`:
```bash
cp backend/.env.example backend/.env
```
Fill out `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `BOT_TOKEN`, `ADMIN_TELEGRAM_IDS` and your preferred `POSTGRES_*` credentials.

### 3. Run with Docker Compose
```bash
cd backend
docker-compose up --build -d
```
The application, database, and background worker will launch simultaneously. Note: Run Alembic migrations natively if the entrypoint does not auto-stamp it.
```bash
docker-compose exec worker alembic upgrade head
```

### 4. Merchant Flow
1. Open your management bot on Telegram.
2. Send `/login` and provide your phone number and OTP code.
3. Use `/create` (or the REST API) to generate a Payment Intent.
4. Wait for the user to transfer the funds to your registered card.
5. Watch the Webhook fire!

## Testing
To run the automated tests locally:
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/
```
All 21+ test cases covering parsing logic, idempotency caps, collision behaviors, and API security should pass successfully.

## License
MIT License. See the LICENSE file for details. 
*Note: Using userbots to scrape messages technically falls into a grey area under Telegram's Terms of Service. Be mindful of usage rate-limits and restrict the listener solely to the official banking bots.*
