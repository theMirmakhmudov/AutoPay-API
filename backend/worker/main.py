import asyncio
import logging
import os

import sentry_sdk
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault

from worker.bot import API_HASH, API_ID, BOT_TOKEN, management_bot, set_client_manager
from worker.client_manager import ClientManager

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

async def cleanup_expired_intents():
    """
    Fix #3 + Background cleanup: Run every 60s to expire old PaymentIntents.
    Started AFTER the event loop is confirmed running.
    """
    from core.database import SessionLocal
    from repositories.payment_repo import PaymentRepository

    while True:
        await asyncio.sleep(60)  # Wait first so loop is fully running
        try:
            db = SessionLocal()
            repo = PaymentRepository(db)
            count = repo.expire_old_intents()
            if count:
                logger.info(f"Expired {count} stale payment intent(s)")
            db.close()
        except Exception as e:
            logger.error(f"Cleanup task error: {e}")

async def run_health_checks(manager: ClientManager):
    """
    Periodically checks the health of all active Telethon userbots.
    If a session is revoked, it updates the DB and notifies the merchant/admin.
    """
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        try:
            await manager.health_check_clients()
        except Exception as e:
            logger.error(f"Health check task error: {e}")

async def main():
    logger.info("Starting Managed Telethon Worker Service...")

    # Database is now managed via Alembic migrations.

    if not BOT_TOKEN:
        logger.error("No MANAGEMENT_BOT_TOKEN provided!")
        return

    # 1. Start the management bot
    await management_bot.start(bot_token=BOT_TOKEN)
    logger.info("✅ Management Bot online")

    # Setup Bot Commands Menu
    try:
        user_cmds = [
            BotCommand(command="start", description="Start the bot and link account"),
            BotCommand(command="credentials", description="View your Merchant ID and Secrets"),
            BotCommand(command="status", description="Check connection status"),
            BotCommand(command="create", description="Generate a payment intent"),
            BotCommand(command="setwebhook", description="Set webhook URL"),
            BotCommand(command="disconnect", description="Disconnect your Telegram account")
        ]
        admin_cmds = [
            BotCommand(command="start", description="Open Admin Control Panel"),
            BotCommand(command="stats", description="View system statistics"),
            BotCommand(command="merchants", description="List all connected merchants"),
            BotCommand(command="ban", description="Ban a merchant")
        ]
        await management_bot(SetBotCommandsRequest(scope=BotCommandScopeDefault(), lang_code='', commands=user_cmds))
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")

    # Fix #3: Create tasks AFTER the loop is running (inside async context)
    asyncio.get_event_loop().create_task(cleanup_expired_intents())

    # 2. Start the Session Manager and inject it into bot for hot-reloading (Fix #4)
    manager = ClientManager(API_ID, API_HASH)
    set_client_manager(manager)  # bot.py can now call manager.start_client()
    await manager.start_all_clients()
    logger.info("✅ All merchant userbots connected")
    
    # Start health check loop
    asyncio.get_event_loop().create_task(run_health_checks(manager))

    # 3. Run indefinitely
    await management_bot.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
