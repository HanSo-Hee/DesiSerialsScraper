# github.com/MrAbhi2k3

import os
import logging
from typing import Optional, Dict, Any
from pyrogram.types import Message
from app.config import get_settings
from app.database.models import EpisodeModel
from app.telegram.client import TelegramClientManager
from app.telegram.keyboards import get_main_channel_keyboard, get_history_keyboard
from app.telegram.messages import format_main_caption, format_history_caption

logger = logging.getLogger(__name__)


class TelegramUploader:
    @staticmethod
    def get_client():
        return TelegramClientManager.client

    @classmethod
    async def upload_to_main_channel(cls, episode: EpisodeModel, video_file_path: Optional[str] = None, poster_file_path: Optional[str] = None, status_message: Optional[Message] = None) -> Dict[str, Any]:
        """Posts new episode to the MAIN channel with poster/thumbnail and inline buttons."""
        client = cls.get_client()
        settings = get_settings()
        bot_username = TelegramClientManager.bot_info.username if TelegramClientManager.bot_info else ""

        caption = format_main_caption(
            show_name=episode.show_name,
            episode_number=episode.episode_number,
            episode_date=episode.episode_date
        )
        reply_markup = get_main_channel_keyboard(bot_username, str(episode.id))

        msg: Optional[Message] = None

        # 1. Reuse existing Telegram file ID if already uploaded
        if episode.telegram_file_id:
            logger.info(f"Reusing existing Telegram file ID: {episode.telegram_file_id}")
            msg = await client.send_video(
                chat_id=settings.MAIN_CHANNEL_ID,
                video=episode.telegram_file_id,
                caption=caption,
                reply_markup=reply_markup
            )
        # 2. Upload video file if available
        elif video_file_path and os.path.exists(video_file_path):
            thumb = poster_file_path if (poster_file_path and os.path.exists(poster_file_path)) else None
            
            progress_cb = None
            if status_message:
                from app.telegram.progress import ProgressTracker
                tracker = ProgressTracker(status_message, action_name="Uploading to Telegram")
                progress_cb = tracker.update

            msg = await client.send_video(
                chat_id=settings.MAIN_CHANNEL_ID,
                video=video_file_path,
                thumb=thumb,
                caption=caption,
                reply_markup=reply_markup,
                progress=progress_cb
            )
        else:
            raise RuntimeError(f"No video file available to upload for episode {episode.id}")

        file_id = None
        file_unique_id = None
        if msg.video:
            file_id = msg.video.file_id
            file_unique_id = msg.video.file_unique_id
        elif msg.document:
            file_id = msg.document.file_id
            file_unique_id = msg.document.file_unique_id

        return {
            "message_id": msg.id,
            "file_id": file_id,
            "file_unique_id": file_unique_id
        }

    @classmethod
    async def copy_to_file_channel(cls, main_message_id: int, file_id: Optional[str] = None, video_file_path: Optional[str] = None) -> Dict[str, Any]:
        """Copies or forwards media permanently into the FILE/ARCHIVE channel."""
        client = cls.get_client()
        settings = get_settings()

        msg: Optional[Message] = None
        try:
            # First attempt copying main channel message directly
            msg = await client.copy_message(
                chat_id=settings.FILE_CHANNEL_ID,
                from_chat_id=settings.MAIN_CHANNEL_ID,
                message_id=main_message_id
            )
        except Exception as e:
            logger.warning(f"Copy message failed from main channel: {e}. Falling back to file ID upload.")
            if file_id:
                msg = await client.send_video(
                    chat_id=settings.FILE_CHANNEL_ID,
                    video=file_id,
                    caption="Archived Media"
                )
            elif video_file_path and os.path.exists(video_file_path):
                msg = await client.send_video(
                    chat_id=settings.FILE_CHANNEL_ID,
                    video=video_file_path,
                    caption="Archived Media"
                )
            else:
                raise RuntimeError("Failed to copy/upload media to FILE channel.")

        # Also mirror media post to LOG_CHANNEL_ID if configured
        if settings.LOG_CHANNEL_ID:
            try:
                await client.copy_message(
                    chat_id=settings.LOG_CHANNEL_ID,
                    from_chat_id=settings.MAIN_CHANNEL_ID,
                    message_id=main_message_id
                )
            except Exception as le:
                logger.warning(f"Failed mirroring message to LOG channel ({settings.LOG_CHANNEL_ID}): {le}")

        ret_file_id = None
        ret_unique_id = None
        if msg.video:
            ret_file_id = msg.video.file_id
            ret_unique_id = msg.video.file_unique_id
        elif msg.document:
            ret_file_id = msg.document.file_id
            ret_unique_id = msg.document.file_unique_id

        return {
            "archive_message_id": msg.id,
            "file_id": ret_file_id,
            "file_unique_id": ret_unique_id
        }

    @classmethod
    async def post_to_history_channel(cls, episode: EpisodeModel, poster_path: Optional[str] = None) -> int:
        """Posts indexed serial metadata entry with GET FILE inline button into HISTORY channel."""
        client = cls.get_client()
        settings = get_settings()

        caption = format_history_caption(
            show_name=episode.show_name,
            episode_number=episode.episode_number,
            episode_date=episode.episode_date
        )
        reply_markup = get_history_keyboard(str(episode.id))

        msg: Optional[Message] = None
        if poster_path and os.path.exists(poster_path):
            msg = await client.send_photo(
                chat_id=settings.HISTORY_CHANNEL_ID,
                photo=poster_path,
                caption=caption,
                reply_markup=reply_markup
            )
        elif episode.poster_url:
            try:
                msg = await client.send_photo(
                    chat_id=settings.HISTORY_CHANNEL_ID,
                    photo=episode.poster_url,
                    caption=caption,
                    reply_markup=reply_markup
                )
            except Exception as e:
                logger.warning(f"Could not send poster URL to history channel: {e}")
                msg = await client.send_message(
                    chat_id=settings.HISTORY_CHANNEL_ID,
                    text=caption,
                    reply_markup=reply_markup
                )
        else:
            msg = await client.send_message(
                chat_id=settings.HISTORY_CHANNEL_ID,
                text=caption,
                reply_markup=reply_markup
            )

        return msg.id

    @classmethod
    async def delete_main_message(cls, message_id: int) -> bool:
        """Deletes original episode message from MAIN channel."""
        client = cls.get_client()
        settings = get_settings()
        try:
            await client.delete_messages(chat_id=settings.MAIN_CHANNEL_ID, message_ids=message_id)
            logger.info(f"Deleted message {message_id} from MAIN channel.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete main message {message_id}: {e}")
            return False

    @classmethod
    async def send_log(cls, text: str):
        """Sends administrative log event notification if LOG_CHANNEL_ID is configured."""
        settings = get_settings()
        if not settings.LOG_CHANNEL_ID:
            return

        client = cls.get_client()
        try:
            await client.send_message(chat_id=settings.LOG_CHANNEL_ID, text=text)
        except Exception as e:
            logger.warning(f"Failed to send log message: {e}")
