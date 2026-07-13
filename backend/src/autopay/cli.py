import argparse
import asyncio
import os
import secrets
import subprocess
import sys
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config


def get_alembic_config():
    """Return the programmatic Alembic config."""
    package_dir = Path(__file__).parent
    alembic_ini_path = package_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(package_dir / "alembic"))
    return alembic_cfg


def init_command(args):
    """Interactive initialization of .env file."""
    if os.path.exists(".env"):
        print("⚠️ A .env file already exists in the current directory.")
        overwrite = input("Do you want to overwrite it? (y/N): ")
        if overwrite.lower() != 'y':
            print("Aborted.")
            return

    print("\n🚀 Welcome to AutopayBot Initialization!")
    print("-" * 40)

    admin_id = input("1. Enter your Telegram Admin ID (e.g., 123456789): ").strip()
    if not admin_id:
        print("Admin ID is required! Aborting.")
        return

    generate_key = input("2. Do you want to automatically generate a secure API_KEY? (Y/n): ").strip().lower()

    if generate_key == 'n':
        api_key = input("   Enter your custom API_KEY: ").strip()
    else:
        api_key = secrets.token_hex(32)
        print(f"   ✅ Generated secure API_KEY: {api_key}")

    env_template = f"""# AvtoPaymentBot Environment Variables
API_KEY={api_key}
ADMIN_ID={admin_id}
DATABASE_URL=sqlite:///./payment_system.db
SENTRY_DSN=
"""
    with open(".env", "w") as f:
        f.write(env_template)

    print("-" * 40)
    print("✅ .env file successfully created!")
    print("Next steps:")
    print("  1. Run 'autopay upgrade' to initialize the database.")
    print("  2. Run 'autopay start' to boot the server and background worker.\n")


def deploy_command(args):
    """Generate a production-ready deployment stack for AutopayBot."""

    if os.path.exists("docker-compose.yml"):
        print("⚠️ A docker-compose.yml file already exists in the current directory.")
        overwrite = input("Do you want to run the wizard again and overwrite it? (y/N): ")
        if overwrite.lower() != 'y':
            print("Aborted. If you just want to update, run: autopay update")
            return

    # Parse existing .env if present
    env_data = {}
    if os.path.exists(".env"):
        with open(".env", "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_data[key.strip()] = val.strip()

    def prompt_env(prompt_msg, key_name):
        default_val = env_data.get(key_name, "")
        if default_val:
            display_prompt = f"{prompt_msg} [{default_val}]: "
        else:
            display_prompt = f"{prompt_msg}: "

        user_input = input(display_prompt).strip()
        return user_input if user_input else default_val

    print("\n" + "═"*70)
    print(" 🛠️  STEP 1: TELEGRAM BOT CONFIGURATION")
    print("═"*70)
    print("Welcome to the Autopay Deploy Wizard. We'll set up your environment step-by-step.\n")

    print("ℹ️ Get your API_ID and API_HASH from https://my.telegram.org (App API ID)")
    api_id = prompt_env("👉 TELEGRAM_API_ID (e.g. 12345678)", "TELEGRAM_API_ID")

    print("\nℹ️ The hash is a long string of letters and numbers from my.telegram.org")
    api_hash = prompt_env("👉 TELEGRAM_API_HASH (e.g. abc123def...)", "TELEGRAM_API_HASH")

    print("\nℹ️ Get your Bot Token by creating a new bot with @BotFather on Telegram")
    bot_token = prompt_env("👉 MANAGEMENT_BOT_TOKEN (e.g. 12345:ABC-DEF...)", "MANAGEMENT_BOT_TOKEN")

    print("\nℹ️ Your personal Telegram User ID (e.g. from @userinfobot) to access the Admin Panel")
    admin_id = prompt_env("👉 ADMIN_TELEGRAM_IDS (e.g. 987654321)", "ADMIN_TELEGRAM_IDS")

    print("\n" + "═"*70)
    print(" ☁️  STEP 2: CLOUDFLARE TUNNEL (Remotely Managed)")
    print("═"*70)
    domain = input("👉 What is your full domain name? (e.g. api.cerifynow.uz) [leave empty to skip]: ").strip()
    # Parse domain dynamically
    parts = domain.split('.')
    if len(parts) > 2:
        subdomain = parts[0]
        root_domain = ".".join(parts[1:])
    else:
        subdomain = "(leave blank)"
        root_domain = domain if domain else "<your-domain>"

    if domain:
        print("\nTo connect your server to your domain without opening ports:")
        print("  1. Go to: https://dash.cloudflare.com/ -> Networking -> Tunnels")
        print("  2. Click 'Create a tunnel' -> Select 'Cloudflared' -> Name it (e.g. autopay_api)")
        print("  3. Copy the long Token (starts with eyJh...) from the 'Install connector' step.")
        print("  4. Click Next (or go to Configure -> Routes -> Add public hostname)")
        print("  5. Fill in the published application form EXACTLY like this:")
        print(f"       - Subdomain (optional) : {subdomain}")
        print(f"       - Domain               : {root_domain}")
        print("       - Service Type         : HTTP")
        print("       - Service URL          : autopay_nginx:80")
        print("  6. Click 'Save hostname'\n")

    tunnel_token = prompt_env("👉 Paste your Cloudflare Tunnel Token (eyJh...)", "CLOUDFLARE_TUNNEL_TOKEN")

    from cryptography.fernet import Fernet
    encryption_key = Fernet.generate_key().decode()

    compose_template = """version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: autopay_db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password123
      POSTGRES_DB: autopay
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  api:
    image: ghcr.io/themirmakhmudov/autopaybot:main
    container_name: autopay_api
    command: sh -c "autopay upgrade && autopay web"
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://postgres:password123@db:5432/autopay
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  worker:
    image: ghcr.io/themirmakhmudov/autopaybot:main
    container_name: autopay_worker
    command: autopay worker
    env_file:
      - .env
    environment:
      - DATABASE_URL=postgresql://postgres:password123@db:5432/autopay
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    container_name: autopay_nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - api
    restart: unless-stopped

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: autopay_tunnel
    restart: always
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - nginx

volumes:
  postgres_data:
"""

    nginx_template = """events {}

http {
    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://api:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto https;
        }
    }
}
"""



    env_template = f"""TELEGRAM_API_ID={api_id}
TELEGRAM_API_HASH={api_hash}
MANAGEMENT_BOT_TOKEN={bot_token}
ADMIN_TELEGRAM_IDS={admin_id}
ENCRYPTION_KEY={encryption_key}
CLOUDFLARE_TUNNEL_TOKEN={tunnel_token}
"""

    # Write files
    os.makedirs("nginx", exist_ok=True)

    with open("docker-compose.yml", "w") as f:
        f.write(compose_template)
    with open("nginx/nginx.conf", "w") as f:
        f.write(nginx_template)

    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write(env_template)
    else:
        # Prompt to overwrite .env
        overwrite_env = input("⚠️ A .env file already exists. Do you want to overwrite it with these new credentials? (y/N): ")
        if overwrite_env.lower() == 'y':
            with open(".env", "w") as f:
                f.write(env_template)

    print("\n✅ Production deployment files generated successfully!")
    print("\n⚠️ IMPORTANT: You are using a Remotely Managed Cloudflare Tunnel.")
    print(f"Make sure you added the Public Hostname in your Cloudflare dashboard for {domain} pointing to http://autopay_nginx:80")
    print("\nTo start your bot in production, run:")
    print("  docker compose up -d --force-recreate")


def update_command(args):
    """Pulls the latest images and restarts the docker containers."""
    if not os.path.exists("docker-compose.yml"):
        print("❌ No docker-compose.yml found. Please run 'autopay deploy' first.")
        return

    print("\n🔄 Updating AutopayBot to the latest version...")
    os.system("docker compose pull && docker compose up -d")
    print("✅ Update complete!\n")


def start_command(args):
    """Start both the FastAPI backend and the background worker simultaneously."""
    print("🚀 Starting AutopayBot Full System...")

    # Run both commands as subprocesses
    web_process = subprocess.Popen([sys.executable, "-m", "autopay", "web", "--host", args.host, "--port", str(args.port)])
    worker_process = subprocess.Popen([sys.executable, "-m", "autopay", "worker"])

    try:
        web_process.wait()
        worker_process.wait()
    except KeyboardInterrupt:
        print("\nStopping AutopayBot...")
        web_process.terminate()
        worker_process.terminate()
        web_process.wait()
        worker_process.wait()
        print("✅ System cleanly shutdown.")


def upgrade_command(args):
    """Run database migrations."""
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")
    print("✅ Database upgraded successfully.")


def web_command(args):
    """Start the FastAPI backend."""
    uvicorn.run("autopay.app:app", host=args.host, port=args.port, reload=args.reload)


def worker_command(args):
    """Start the Telethon userbot background worker."""
    from autopay.worker.main import main as run_worker

    print("Starting Autopay background worker...")
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\nWorker stopped by user.")


def main():
    parser = argparse.ArgumentParser(description="Autopay Bot Management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # init
    parser_init = subparsers.add_parser("init", help="Interactive .env configuration wizard")

    # deploy
    parser_deploy = subparsers.add_parser("deploy", help="Generate docker-compose.yml for production deployment")

    # start
    parser_start = subparsers.add_parser("start", help="Boot both Web API and Background Worker simultaneously")
    parser_start.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser_start.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")

    # upgrade
    parser_upgrade = subparsers.add_parser("upgrade", help="Run database migrations")

    # web
    parser_web = subparsers.add_parser("web", help="Start the FastAPI web server only")
    parser_web.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser_web.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser_web.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # worker
    parser_worker = subparsers.add_parser("worker", help="Start the background worker only")

    # update
    parser_update = subparsers.add_parser("update", help="Pull latest images and restart Docker containers")

    args = parser.parse_args()

    if args.command == "init":
        init_command(args)
    elif args.command == "deploy":
        deploy_command(args)
    elif args.command == "update":
        update_command(args)
    elif args.command == "start":
        start_command(args)
    elif args.command == "upgrade":
        upgrade_command(args)
    elif args.command == "web":
        web_command(args)
    elif args.command == "worker":
        worker_command(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
