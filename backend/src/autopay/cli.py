import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

import uvicorn
from alembic import command
from alembic.config import Config


def get_alembic_config():
    """Return the programmatic Alembic config."""
    # Find the alembic.ini packaged with the installation
    package_dir = Path(__file__).parent
    alembic_ini_path = package_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    # We must explicitly set the script location so it knows where to find versions
    alembic_cfg.set_main_option("script_location", str(package_dir / "alembic"))
    return alembic_cfg


def init_command(args):
    """Initialize a default .env file in the current directory."""
    if os.path.exists(".env"):
        print("A .env file already exists in the current directory.")
        return

    env_template = """# AvtoPaymentBot Environment Variables
API_KEY=your_secure_api_key_here
ADMIN_ID=123456789
DATABASE_URL=sqlite:///./payment_system.db
SENTRY_DSN=
"""
    with open(".env", "w") as f:
        f.write(env_template)
    print("Created .env file. Please configure your API_KEY and ADMIN_ID.")


def upgrade_command(args):
    """Run database migrations."""
    alembic_cfg = get_alembic_config()
    command.upgrade(alembic_cfg, "head")
    print("Database upgraded successfully.")


def web_command(args):
    """Start the FastAPI backend."""
    # We run it as a module
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
    parser_init = subparsers.add_parser("init", help="Initialize .env configuration")

    # upgrade
    parser_upgrade = subparsers.add_parser("upgrade", help="Run database migrations")

    # web
    parser_web = subparsers.add_parser("web", help="Start the FastAPI web server")
    parser_web.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser_web.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    parser_web.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # worker
    parser_worker = subparsers.add_parser("worker", help="Start the background worker")

    args = parser.parse_args()

    if args.command == "init":
        init_command(args)
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
