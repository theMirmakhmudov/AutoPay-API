# Autopaybot (AvtoPaymentBot)

A Telegram-based automated payment detection system designed specifically for the Uzbekistan market. This application uses Telegram Userbots via the Telethon library to intercept incoming transaction notifications from payment systems (Click, Payme, Uzcard, Humo) on behalf of merchants. It acts as an integration middleware, parsing transaction SMS/Messages and automatically firing Webhooks to your backend server.

## Features
- **Multi-Merchant Support:** Manages concurrent Telegram Userbots for multiple independent merchants dynamically.
- **Smart Payment Parser:** Uses regex to interpret and normalize transaction amounts from Click, Payme, Uzcard, and Humo notification bots.
- **Collision Management (Uzbekistan UX):** Temporarily augments subsequent identical transaction requests by exactly +1 UZS (100 tiyins) to maintain uniqueness for idempotent processing without using decimals, since popular Uzbek banking apps don't support fractional inputs.
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

### 2. Initialization Wizard
Initialize the project to create your `.env` configuration file interactively:
```bash
autopay init
```
*This command acts as a setup wizard. It will prompt you for your `ADMIN_ID` and can automatically generate a cryptographically secure 64-character `API_KEY` for you.*

### 3. Database Migrations
Run the embedded Alembic migrations to set up your PostgreSQL database:
```bash
autopay upgrade
```

### 4. Run the System
You no longer need to open two terminals! Run the unified start command to boot both the FastAPI Web Server and the Telegram Background Worker simultaneously:

```bash
autopay start
```
*(Press `Ctrl+C` to safely shut down both processes).*

---

## 🐳 Docker Deployment (One-Click)

Don't want to install Python packages directly or want to deploy to a Linux server safely? You can use our interactive Docker scaffolding tool!

Simply run:
```bash
autopay deploy
```
This command will instantly generate a production-ready `docker-compose.yml` file pointing to our official GitHub Container Registry image (`ghcr.io/themirmakhmudov/autopaybot:latest`).

Then, just bring it up:
```bash
docker-compose up -d
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
