# github.com/MrAbhi2k3

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_channel_keyboard(bot_username: str, episode_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard attached to main channel posts."""
    url = f"https://t.me/{bot_username}?start=get_{episode_id}" if bot_username else "#"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ WATCH / GET FILE", url=url)]
    ])


def get_history_keyboard(episode_id: str) -> InlineKeyboardMarkup:
    """Inline keyboard attached to history channel posts."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 GET FILE", callback_data=f"get_ep:{episode_id}")]
    ])
