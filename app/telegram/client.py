# github.com/MrAbhi2k3

import logging
from typing import Optional
from pyrogram import Client
from pyrogram.errors import RPCError
from app.config import get_settings

logger = logging.getLogger(__name__)


class TelegramClientManager:
    client: Optional[Client] = None
    bot_info = None

    @classmethod
    async def initialize(cls) -> Client:
        settings = get_settings()
        logger.info("Initializing PyroBlack Telegram Client...")
        cls.client = Client(
            name="serial_auto_uploader_bot",
            api_id=settings.API_ID,
            api_hash=settings.API_HASH,
            bot_token=settings.BOT_TOKEN,
            max_concurrent_transmissions=1,
            ipv6=False,
            workdir="./downloads"
        )
        await cls.client.start()
        cls.bot_info = await cls.client.get_me()
        logger.info(f"Telegram Bot started as @{cls.bot_info.username} (ID: {cls.bot_info.id})")
        return cls.client

    @classmethod
    async def stop(cls):
        if cls.client and cls.client.is_connected:
            await cls.client.stop()
            logger.info("Telegram Client stopped.")

    @classmethod
    async def verify_channel_permissions(cls) -> dict:
        """Verifies bot's presence and permissions in target Telegram channels."""
        if not cls.client:
            raise RuntimeError("Telegram client not started.")

        settings = get_settings()
        results = {"main": False, "file": False, "history": False, "log": False}

        # Check Main Channel
        try:
            chat = await cls.client.get_chat(settings.MAIN_CHANNEL_ID)
            results["main"] = True
            logger.info(f"Verified Main Channel access: {chat.title}")
        except Exception as e:
            logger.error(f"Failed to access MAIN_CHANNEL_ID {settings.MAIN_CHANNEL_ID}: {e}")

        # Check File Channel
        try:
            chat = await cls.client.get_chat(settings.FILE_CHANNEL_ID)
            results["file"] = True
            logger.info(f"Verified File Channel access: {chat.title}")
        except Exception as e:
            logger.error(f"Failed to access FILE_CHANNEL_ID {settings.FILE_CHANNEL_ID}: {e}")

        # Check History Channel
        try:
            chat = await cls.client.get_chat(settings.HISTORY_CHANNEL_ID)
            results["history"] = True
            logger.info(f"Verified History Channel access: {chat.title}")
        except Exception as e:
            logger.error(f"Failed to access HISTORY_CHANNEL_ID {settings.HISTORY_CHANNEL_ID}: {e}")

        # Check Log Channel if provided
        if settings.LOG_CHANNEL_ID:
            try:
                chat = await cls.client.get_chat(settings.LOG_CHANNEL_ID)
                results["log"] = True
                logger.info(f"Verified Log Channel access: {chat.title}")
            except Exception as e:
                logger.warning(f"Failed to access LOG_CHANNEL_ID {settings.LOG_CHANNEL_ID}: {e}")
        else:
            results["log"] = True

        return results
