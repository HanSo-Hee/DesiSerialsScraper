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


async def _start_health_server():
    from aiohttp import web

    async def handle_ping(request):
        return web.Response(text="OK", content_type="text/plain")

    server_app = web.Application()
    server_app.router.add_get("/", handle_ping)
    server_app.router.add_get("/health", handle_ping)
    runner = web.AppRunner(server_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    logger.info("Health check server listening on http://0.0.0.0:8000/health")
    return runner


async def start_app():
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    logger.info("Starting Serial Auto Uploader Application...")

    try:
        await MongoDB.connect()
    except Exception as e:
        logger.critical(f"MongoDB connection failed: {e}")
        sys.exit(1)

    try:
        app = await TelegramClientManager.initialize()
        register_handlers(app)
        perms = await TelegramClientManager.verify_channel_permissions()
    except Exception as e:
        logger.critical(f"Telegram client initialization failed: {e}")
        sys.exit(1)

    main_ok = "OK" if perms.get("main") else "FAILED"
    file_ok = "OK" if perms.get("file") else "FAILED"
    history_ok = "OK" if perms.get("history") else "FAILED"
    log_ok = "OK" if perms.get("log") else "DISABLED"

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
    print(f"Scheduler     : IST-AWARE")
    print(f"Delete After  : {settings.DELETE_AFTER_HOURS} hours")
    print("=" * 40 + "\n")

    service = EpisodeService()
    await service.recover_stuck_episodes()

    SchedulerManager.initialize()

    runner = await _start_health_server()

    stop_event = asyncio.Event()

    def _handle_signal():
        stop_event.set()

    loop = asyncio.get_running_loop()
    try:
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_signal)
    except NotImplementedError:
        pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        logger.info("Shutdown signal received. Cleaning up...")
        SchedulerManager.shutdown()
        await TelegramClientManager.stop()
        await MongoDB.close()
        await runner.cleanup()
        logger.info("Application shutdown complete.")
