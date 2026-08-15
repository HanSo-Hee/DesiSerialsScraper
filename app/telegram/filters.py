# github.com/MrAbhi2k3

import pyrogram
from pyrogram import filters
from app.config import get_settings


def admin_filter():
    """Custom filter restricting command execution to configured ADMIN_IDS."""
    async def func(_, __, message: pyrogram.types.Message):
        settings = get_settings()
        if not message.from_user:
            return False
        return message.from_user.id in settings.ADMIN_IDS

    return filters.create(func, "AdminFilter")
