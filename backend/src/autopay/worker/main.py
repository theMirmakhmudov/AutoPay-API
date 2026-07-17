import asyncio
import logging
import os

import sentry_sdk

from autopay.core.config import settings
from autopay.worker.aiogram_bot import API_HASH, API_ID, bot, dp, set_client_manager, set_menus
from autopay.worker.client_manager import ClientManager

BOT_TOKEN = settings.MANAGEMENT_BOT_TOKEN

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        traces_sample_rate=1.0,
    )

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def cleanup_expired_intents():
    """
    Fix #3 + Background cleanup: Run every 60s to expire old PaymentIntents.
    Started AFTER the event loop is confirmed running.
    """
    from autopay.core.database import SessionLocal
    from autopay.repositories.payment_repo import PaymentRepository

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
    logger.info("Starting Managed Aiogram Worker Service...")

    if not BOT_TOKEN:
        logger.error("No MANAGEMENT_BOT_TOKEN provided!")
        return

    # 1. Start the management bot commands
    await set_menus()
    logger.info("✅ Management Bot commands updated")

    # Fix #3: Create tasks AFTER the loop is running (inside async context)
    asyncio.get_event_loop().create_task(cleanup_expired_intents())

    # 2. Start the Session Manager and inject it into bot for hot-reloading (Fix #4)
    manager = ClientManager(API_ID, API_HASH)
    set_client_manager(manager)
    await manager.start_all_clients()
    logger.info("✅ All merchant userbots connected")

    # Start health check loop
    asyncio.get_event_loop().create_task(run_health_checks(manager))

    # 3. Run indefinitely with aiogram polling
    logger.info("Starting Aiogram polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
