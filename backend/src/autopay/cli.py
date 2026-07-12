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
    """Generate a docker-compose.yml file for server deployment."""
    if os.path.exists("docker-compose.yml"):
        print("⚠️ A docker-compose.yml file already exists in the current directory.")
        overwrite = input("Do you want to overwrite it? (y/N): ")
        if overwrite.lower() != 'y':
            print("Aborted.")
            return

    compose_template = """version: '3.8'

services:
  autopay_api:
    image: ghcr.io/themirmakhmudov/autopaybot:latest
    container_name: autopay_api
    restart: always
    env_file:
      - .env
    command: ["autopay", "web", "--host", "0.0.0.0", "--port", "8000"]
    ports:
      - "8000:8000"
    volumes:
      - ./payment_system.db:/app/payment_system.db

  autopay_worker:
    image: ghcr.io/themirmakhmudov/autopaybot:latest
    container_name: autopay_worker
    restart: always
    env_file:
      - .env
    command: ["autopay", "worker"]
    volumes:
      - ./payment_system.db:/app/payment_system.db
"""
    with open("docker-compose.yml", "w") as f:
        f.write(compose_template)
    
    print("✅ docker-compose.yml generated successfully!")
    print("To start your bot in production, just run:")
    print("  docker-compose up -d")


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
    from autopay.worker.main import run_worker

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

    args = parser.parse_args()

    if args.command == "init":
        init_command(args)
    elif args.command == "deploy":
        deploy_command(args)
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
