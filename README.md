# Autopaybot (AvtoPaymentBot)

A Telegram-based automated payment detection system designed specifically for the Uzbekistan market. This application uses Telegram Userbots via the Telethon library to intercept incoming transaction notifications from payment systems (Click, Payme, Uzcard, Humo) on behalf of merchants. It acts as an integration middleware, parsing transaction SMS/Messages and automatically firing Webhooks to your backend server.

## Features
- **Multi-Merchant Support:** Manages concurrent Telegram Userbots for multiple independent merchants dynamically.
- **Smart Payment Parser:** Uses regex to interpret and normalize transaction amounts from Click, Payme, Uzcard, and Humo notification bots.
- **Collision Management:** Temporarily augments subsequent identical transaction requests by tiny fractions (+0.01 UZS offset) to maintain uniqueness for idempotent processing.
- **Webhook Integration:** Instantly fires asynchronous HTTP webhooks signed with an HMAC (SHA-256) signature.
- **Background Health Checking:** Asynchronous daemon runs every 5 minutes to verify if merchant sessions have been revoked.

---

## 🚀 Installation & Usage

You can run `autopaybot` anywhere by simply installing it via `pip`.

### 1. Install via pip
```bash
pip install autopaybot
```
*Note: Python 3.11+ is required.*

### 2. Initialization
Initialize the project to create your `.env` configuration file:
```bash
autopay init
```
*Fill out `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `BOT_TOKEN`, `ADMIN_TELEGRAM_IDS` and your preferred `POSTGRES_*` credentials.*

### 3. Database Migrations
Run the embedded Alembic migrations to set up your PostgreSQL database:
```bash
autopay upgrade
```

### 4. Run the Services
You need to run two separate processes (the API and the Telegram Worker):

**Start the Web API:**
```bash
autopay web
```

**Start the Telegram Worker:**
```bash
autopay worker
```

---

## 🐳 Docker Deployment

Don't want to install Python packages directly? You can use the official pre-built Docker image from the GitHub Container Registry!

```bash
docker pull ghcr.io/themirmakhmudov/autopaybot:latest
```

**Run the API:**
```bash
docker run --env-file .env -p 8000:8000 ghcr.io/themirmakhmudov/autopaybot:latest autopay web
```

**Run the Worker:**
```bash
docker run --env-file .env ghcr.io/themirmakhmudov/autopaybot:latest autopay worker
```

---

## Testing & Development

To contribute or run automated tests locally:
```bash
git clone https://github.com/theMirmakhmudov/AutoPay-API.git
cd AutoPay-API/backend

# Install with development dependencies
pip install -e .[dev]

# Run tests
pytest tests/ -v
```

## License
MIT License. See the LICENSE file for details. 
*Note: Using userbots to scrape messages technically falls into a grey area under Telegram's Terms of Service. Be mindful of usage rate-limits and restrict the listener solely to the official banking bots.*
