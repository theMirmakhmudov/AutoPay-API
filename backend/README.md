<div align="center">
  <h1>🚀 Autopaybot (AvtoPaymentBot)</h1>
  
  <p><b>A Telegram-based automated payment detection system designed specifically for the Uzbekistan market.</b></p>

  [![Unified CI/CD Pipeline](https://github.com/theMirmakhmudov/AutoPay-API/actions/workflows/pipeline.yml/badge.svg)](https://github.com/theMirmakhmudov/AutoPay-API/actions/workflows/pipeline.yml)
  [![PyPI version](https://badge.fury.io/py/autopaybot.svg)](https://pypi.org/project/autopaybot/)
  ![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
  ![License](https://img.shields.io/badge/license-MIT-green.svg)
</div>

---

This application uses Telegram Userbots via the **Telethon** library to intercept incoming transaction notifications exclusively from the **@humocardbot** payment system on behalf of merchants. It acts as an integration middleware: parsing transaction SMS/Messages in real-time and automatically firing **Webhooks** to your backend server.

## ✨ Features

- 🏢 **Multi-Merchant Support:** Manages concurrent Telegram Userbots for multiple independent merchants dynamically.
- 🔒 **Private Whitelisting (Closed Bot):** The bot is completely closed to the public. The main administrator must explicitly add a new merchant's Telegram ID via the **Admin Control Panel** before they can register.
- 🧠 **Smart Payment Parser:** Uses advanced regex to instantly interpret and normalize transaction amounts specifically from the **@humocardbot**.
- 🎯 **Strict Card Monitoring:** Merchants can explicitly set their receiving card's last 4 digits (e.g., `*4183`) using the `/setcard` command to prevent false positives from other outgoing or unrelated transactions.
- ⚡ **Collision Management (Uzbekistan UX):** Temporarily augments subsequent identical transaction requests by exactly +1 UZS (100 tiyins) to maintain uniqueness for idempotent processing without using decimals, bypassing the fractional input limitations of popular Uzbek banking apps.
- 🔗 **Secure Webhook Integration:** Instantly fires asynchronous HTTP webhooks signed with an HMAC (SHA-256) signature for verified backend processing.
- 🛡️ **Background Health Checking:** An asynchronous daemon runs every 5 minutes to verify if merchant sessions are active and automatically restarts broken connections.
- ☁️ **Cloudflare Tunnel Ready:** Built-in tools to seamlessly connect your local or VPS deployments to the public internet securely using Cloudflare Tunnels (Zero Trust) without opening any ports.

---

## 🐳 Docker Deployment (Recommended)

To deploy securely to a Linux VPS, use the interactive wizard which sets up Docker Compose, NGINX, and Cloudflare Tunnels automatically.

### 1. Initial Setup (Wizard)
Run the built-in wizard. It will interactively ask for your Telegram API credentials and Cloudflare Tunnel token, generating `.env`, `docker-compose.yml`, and `nginx/nginx.conf` for you:

```bash
pip install autopaybot
autopay deploy
```
*(Follow the interactive terminal instructions to complete the setup)*

### 2. Start the Server
Once the wizard completes, bring up the containers in the background:
```bash
docker compose up -d
```
*(The system runs on `ghcr.io/themirmakhmudov/autopaybot:main`)*

### 3. Upgrading to a New Version
When a new version is released on GitHub, **you do NOT need to run `autopay deploy` again.** All your configurations are safely stored in `.env`.
To update your server, simply pull the latest image and restart:
```bash
docker compose pull
docker compose up -d
```

---

## 🤖 Telegram Bot Usage

Search for your bot on Telegram (using the Bot Token you provided during setup) and send `/start`.

### For Administrators
If your Telegram ID matches `ADMIN_TELEGRAM_IDS` in the `.env` file, sending `/start` will open the **Admin Control Panel**. 
From here, you can:
- **➕ Add Merchant:** Whitelist a new user by entering their Telegram ID. Only whitelisted users can connect their accounts!
- **📊 Stats:** View system-wide statistics (active merchants, total payments processed).
- **👥 Merchants:** See a list of all registered merchants and their connection status.
- **📢 Broadcast:** Send a message to all connected merchants.

### For Merchants
Once a merchant's Telegram ID is whitelisted by the Admin, they can send `/start` to the bot. 
The bot will guide them to:
1. Send their phone number.
2. Enter the Telegram Login Code to authenticate the Userbot.
3. Once connected, they can generate payment links (`/create`), view their credentials (`/credentials`), and set their destination webhook (`/setwebhook`).
4. **Crucially**, they must link their receiving card (`/setcard *4183`) so the bot knows which incoming transactions to process! If you want to disable card filtering, you can use `/unsetcard`.

---

## 🚀 Local Installation (Without Docker)

You can run `autopaybot` directly on your host machine for development or testing.

### 1. Install via pip
```bash
pip install autopaybot
```
*(Note: Python 3.11+ is required)*

### 2. Initialization Wizard
Initialize the project to create your `.env` configuration file interactively:
```bash
autopay init
```

### 3. Database Migrations
Run the embedded Alembic migrations to set up your PostgreSQL (or SQLite) database:
```bash
autopay upgrade
```

### 4. Run the System
Run the unified start command to boot both the FastAPI Web Server and the Telegram Background Worker simultaneously:
```bash
autopay start
```
*(Press `Ctrl+C` to safely shut down both processes).*

---

## 🛠️ Testing & Development

To contribute or run automated tests locally:

```bash
# Clone the repository
git clone https://github.com/theMirmakhmudov/AutoPay-API.git
cd AutoPay-API/backend

# Install with development and testing dependencies
pip install -e .[dev]

# Run tests with coverage
pytest tests/ -v
```

---

## 📝 License & Disclaimer

**MIT License.** See the `LICENSE` file for details. 

> ⚠️ **Disclaimer:** Using userbots to scrape messages technically falls into a grey area under Telegram's Terms of Service. Be mindful of usage rate-limits and restrict the listener solely to the official banking bots to avoid account restrictions.
