# github.com/MrAbhi2k3

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from app.database.models import EpisodeModel, EpisodeStatus
from app.database.repositories import EpisodeRepository
from app.media.downloader import MediaDownloader
from app.media.cleanup import cleanup_file
from app.telegram.uploader import TelegramUploader

logger = logging.getLogger(__name__)


class ArchiveService:
    @classmethod
    async def process_due_archives(cls):
        """Processes episodes whose 12-hour main channel retention period has expired."""
        now = datetime.now(timezone.utc)
        due_episodes = await EpisodeRepository.get_due_for_archive(now)
        if not due_episodes:
            logger.debug("No episodes currently due for archiving.")
            return

        logger.info(f"Found {len(due_episodes)} episodes due for archiving.")
        for episode in due_episodes:
            await cls.archive_single_episode(episode)

    @classmethod
    async def archive_single_episode(cls, episode: EpisodeModel):
        """
        Executes strict zero-data-loss archive workflow:
        1. Find pending episode
        2. Verify main message exists
        3. Archive/copy media into FILE channel
        4. Verify archive message exists
        5. Save archive message ID & Telegram file ID
        6. Create HISTORY post
        7. Verify HISTORY post exists
        8. Delete MAIN message
        9. Mark DELETED_FROM_MAIN
        """
        if not episode.telegram_main_message_id:
            logger.error(f"Cannot archive episode {episode.id}: missing main message ID.")
            return

        poster_path: Optional[str] = None
        try:
            logger.info(f"Beginning archival for episode {episode.id}: {episode.show_name} Ep {episode.episode_number}")

            # 1. Copy/Archive media into FILE channel
            archive_res = await TelegramUploader.copy_to_file_channel(
                main_message_id=episode.telegram_main_message_id,
                file_id=episode.telegram_file_id
            )

            archive_msg_id = archive_res["archive_message_id"]
            telegram_file_id = archive_res["file_id"] or episode.telegram_file_id
            telegram_file_unique_id = archive_res["file_unique_id"] or episode.telegram_file_unique_id

            if not archive_msg_id:
                raise RuntimeError("Archive operation failed: invalid archive message ID received.")

            # Download poster locally if needed for history post
            downloader = MediaDownloader()
            if episode.poster_url:
                try:
                    poster_path = await downloader.download_file(episode.poster_url, custom_filename=f"hist_poster_{episode.id}.jpg")
                except Exception as e:
                    logger.warning(f"Could not download poster for history post {episode.id}: {e}")

            # 2. Create HISTORY channel post
            history_msg_id = await TelegramUploader.post_to_history_channel(
                episode=episode,
                poster_path=poster_path
            )

            if not history_msg_id:
                raise RuntimeError("History post creation failed: invalid history message ID received.")

            now = datetime.now(timezone.utc)
            # Update status to ARCHIVED
            await EpisodeRepository.update_status(
                episode.id,
                status=EpisodeStatus.ARCHIVED,
                telegram_archive_message_id=archive_msg_id,
                telegram_history_message_id=history_msg_id,
                telegram_file_id=telegram_file_id,
                telegram_file_unique_id=telegram_file_unique_id,
                archived_at=now
            )
            logger.info(f"Episode {episode.id} media safely archived in FILE and HISTORY channels.")

            # 3. ONLY THEN delete original message from MAIN channel
            deleted = await TelegramUploader.delete_main_message(episode.telegram_main_message_id)
            if deleted:
                await EpisodeRepository.update_status(
                    episode.id,
                    status=EpisodeStatus.DELETED_FROM_MAIN,
                    deleted_at=now
                )
                logger.info(f"Episode {episode.id} safely removed from MAIN channel.")
                await TelegramUploader.send_log(
                    f"📦 ARCHIVED & DELETED FROM MAIN\n📺 {episode.show_name}\n🎬 Episode {episode.episode_number}"
                )

        except Exception as e:
            error_msg = f"Archive workflow failed for episode {episode.id}: {e}"
            logger.error(error_msg, exc_info=True)
            await EpisodeRepository.record_error(episode.id, str(e), status=EpisodeStatus.ARCHIVE_PENDING)
            await TelegramUploader.send_log(f"❌ ARCHIVE ERROR\n📺 {episode.show_name}\nReason: {e}")
        finally:
            if poster_path:
                cleanup_file(poster_path)
