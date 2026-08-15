# github.com/MrAbhi2k3

import asyncio
import logging
import sys
from app.config import get_settings
from app.logging import setup_logging
from app.database.mongodb import MongoDB
from app.telegram.client import TelegramClientManager
from app.telegram.handlers import register_handlers
from app.scheduler.manager import SchedulerManager
from app.services.episode_service import EpisodeService

logger = logging.getLogger(__name__)


async def start_app():
    # 1. Load settings and setup logging
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    logger.info("Starting Serial Auto Uploader Application...")

    # 2. Initialize Database
    try:
        await MongoDB.connect()
    except Exception as e:
        logger.critical(f"MongoDB connection failed: {e}")
        sys.exit(1)

    # 3. Initialize Telegram Bot via PyroBlack
    try:
        app = await TelegramClientManager.initialize()
        register_handlers(app)
        perms = await TelegramClientManager.verify_channel_permissions()
    except Exception as e:
        logger.critical(f"Telegram client initialization failed: {e}")
        sys.exit(1)

    # 4. Display Startup Banner
    main_ok = "OK" if perms.get("main") else "FAILED"
    file_ok = "OK" if perms.get("file") else "FAILED"
    history_ok = "OK" if perms.get("history") else "FAILED"
    log_ok = "OK" if perms.get("log") else "DISABLED/FAILED"

    print("\n" + "=" * 40)
    print(" SERIAL AUTO UPLOADER")
    print("=" * 40)
    print(f"MongoDB       : CONNECTED")
    print(f"Telegram      : CONNECTED")
    print(f"Main Channel  : {main_ok}")
    print(f"File Channel  : {file_ok}")
    print(f"History       : {history_ok}")
    print(f"Log Channel   : {log_ok}")
    print(f"Scraper       : ENABLED")
    print(f"Scheduler     : ENABLED")
    print(f"Delete After  : {settings.DELETE_AFTER_HOURS} hours")
    print("=" * 40 + "\n")

    # 5. Startup Recovery
    service = EpisodeService()
    await service.recover_stuck_episodes()

    # 6. Start Scheduler
    SchedulerManager.initialize()

    # Keep application running asynchronously
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received.")
    finally:
        SchedulerManager.shutdown()
        await TelegramClientManager.stop()
        await MongoDB.close()
        logger.info("Application shutdown complete.")
