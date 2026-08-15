# github.com/MrAbhi2k3

import logging
from typing import List, Tuple
from pyrogram import Client
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.config import get_settings

logger = logging.getLogger(__name__)


class ForceSubManager:
    @staticmethod
    async def check_user_joined(client: Client, user_id: int) -> Tuple[bool, List[Tuple[int, str]]]:
        """Checks if a user has joined all required force channels."""
        settings = get_settings()
        missing_channels: List[Tuple[int, str]] = []

        if not settings.FORCE_SUB_CHANNELS:
            return True, []

        for channel_id in settings.FORCE_SUB_CHANNELS:
            try:
                member = await client.get_chat_member(chat_id=channel_id, user_id=user_id)
                if member.status not in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER):
                    chat = await client.get_chat(channel_id)
                    invite_link = chat.invite_link or f"https://t.me/c/{str(channel_id).replace('-100', '')}/1"
                    missing_channels.append((channel_id, invite_link))
            except Exception as e:
                logger.warning(f"Force sub check error for channel {channel_id}: {e}")
                try:
                    chat = await client.get_chat(channel_id)
                    invite_link = chat.invite_link or f"https://t.me/c/{str(channel_id).replace('-100', '')}/1"
                    missing_channels.append((channel_id, invite_link))
                except Exception:
                    pass

        return len(missing_channels) == 0, missing_channels

    @staticmethod
    def build_fsub_keyboard(missing_channels: List[Tuple[int, str]], callback_data: str) -> InlineKeyboardMarkup:
        buttons = []
        for idx, (ch_id, invite_link) in enumerate(missing_channels, start=1):
            buttons.append([InlineKeyboardButton(f"📢 Join Channel #{idx}", url=invite_link)])
        
        buttons.append([InlineKeyboardButton("🔄 Try Again / Verify", callback_data=callback_data)])
        return InlineKeyboardMarkup(buttons)
