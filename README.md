<div align="center">
  <h1>🚀 Autopaybot (AvtoPaymentBot)</h1>
  
  <p><b>A Telegram-based automated payment detection system designed specifically for the Uzbekistan market.</b></p>

  [![Unified CI/CD Pipeline](https://github.com/theMirmakhmudov/AutoPay-API/actions/workflows/pipeline.yml/badge.svg)](https://github.com/theMirmakhmudov/AutoPay-API/actions/workflows/pipeline.yml)
  [![PyPI version](https://badge.fury.io/py/autopaybot.svg)](https://pypi.org/project/autopaybot/)
  ![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
  ![License](https://img.shields.io/badge/license-MIT-green.svg)
</div>

---

This application uses Telegram Userbots via the **Telethon** library to intercept incoming transaction notifications from popular payment systems (Click, Payme, Uzcard, Humo) on behalf of merchants. It acts as an integration middleware: parsing transaction SMS/Messages in real-time and automatically firing **Webhooks** to your backend server.

## ✨ Features

- 🏢 **Multi-Merchant Support:** Manages concurrent Telegram Userbots for multiple independent merchants dynamically.
- 🧠 **Smart Payment Parser:** Uses advanced regex to instantly interpret and normalize transaction amounts from Click, Payme, Uzcard, Humo, and CardXabar notification bots.
- ⚡ **Collision Management (Uzbekistan UX):** Temporarily augments subsequent identical transaction requests by exactly +1 UZS (100 tiyins) to maintain uniqueness for idempotent processing without using decimals, bypassing the fractional input limitations of popular Uzbek banking apps.
- 🔗 **Secure Webhook Integration:** Instantly fires asynchronous HTTP webhooks signed with an HMAC (SHA-256) signature for verified backend processing.
- 🛡️ **Background Health Checking:** An asynchronous daemon runs every 5 minutes to verify if merchant sessions are active and automatically restarts broken connections.

---

## 🚀 Installation & Quick Start

You can run `autopaybot` anywhere by simply installing it via `pip`.

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
*This setup wizard will prompt you for your `ADMIN_ID` and can automatically generate a cryptographically secure 64-character `API_KEY` for you.*

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

## 🐳 Docker Deployment (Recommended)

Don't want to install Python packages directly? Want to deploy to a Linux VPS safely? Use our interactive Docker scaffolding tool!

1. Generate a production-ready `docker-compose.yml` pointing to our official GitHub Container Registry image:
   ```bash
   autopay deploy
   ```
2. Bring up the containers in the background:
   ```bash
   docker-compose up -d
   ```

*(Image: `ghcr.io/themirmakhmudov/autopaybot:latest`)*

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
