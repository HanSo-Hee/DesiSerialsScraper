# github.com/MrAbhi2k3

import os
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from app.config import get_settings
from app.database.models import EpisodeModel, EpisodeStatus
from app.database.repositories import EpisodeRepository
from app.media.downloader import MediaDownloader
from app.media.cleanup import cleanup_file
from app.scraper.service import ScraperService
from app.telegram.uploader import TelegramUploader

logger = logging.getLogger(__name__)


class EpisodeService:
    def __init__(self):
        self.downloader = MediaDownloader()
        self.scraper_service = ScraperService()

    async def run_scraper_pipeline(self) -> int:
        """Executes scraper scan and ingests newly detected episodes."""
        logger.info("Running automated scraper pipeline...")
        new_episodes = await self.scraper_service.scan_and_ingest()
        logger.info(f"Scraper pipeline complete. {len(new_episodes)} new episodes ingested.")
        
        # Trigger immediate processing for newly ingested episodes
        if new_episodes:
            asyncio.create_task(self.process_detected_episodes())
        return len(new_episodes)

    async def process_detected_episodes(self):
        """Processes all episodes in DETECTED state sequentially with concurrency limits."""
        detected = await EpisodeRepository.get_by_status(EpisodeStatus.DETECTED)
        if not detected:
            logger.debug("No DETECTED episodes waiting for upload.")
            return

        logger.info(f"Processing {len(detected)} DETECTED episodes...")
        for ep in detected:
            await self.process_single_episode(ep)

    async def process_single_episode(self, episode: EpisodeModel, status_message: Optional[Any] = None):
        """Atomically transitions state and uploads episode to MAIN channel."""
        acquired = await EpisodeRepository.try_acquire_lock(
            episode.id,
            current_status=EpisodeStatus.DETECTED,
            target_status=EpisodeStatus.DOWNLOADING
        )
        if not acquired:
            logger.debug(f"Episode {episode.id} already being processed by another task.")
            return

        video_path: Optional[str] = None
        poster_path: Optional[str] = None

        try:
            if episode.media_url and not episode.telegram_file_id:
                try:
                    from app.scraper.resolver import StreamResolver
                    resolved_url = await StreamResolver.resolve_stream_url(episode.media_url)
                    clean_name = f"{episode.show_name} Ep {episode.episode_number} [@tellyfun_official].mp4".replace("/", "-")
                    video_filename = clean_name
                    video_path = await self.downloader.download_file(
                        resolved_url,
                        custom_filename=video_filename,
                        status_message=status_message
                    )
                except Exception as e:
                    logger.warning(f"Could not download video file for episode {episode.id}: {e}")

            if episode.poster_url:
                try:
                    poster_filename = f"poster_{episode.id}.jpg"
                    poster_path = await self.downloader.download_file(episode.poster_url, custom_filename=poster_filename)
                except Exception as e:
                    logger.warning(f"Could not download poster image for episode {episode.id}: {e}")

            # 3. Transition to UPLOADING
            await EpisodeRepository.update_status(episode.id, EpisodeStatus.UPLOADING)

            # 4. Upload to MAIN channel
            upload_res = await TelegramUploader.upload_to_main_channel(
                episode=episode,
                video_file_path=video_path,
                poster_file_path=poster_path,
                status_message=status_message
            )

            main_msg_id = upload_res["message_id"]
            file_id = upload_res["file_id"]
            file_unique_id = upload_res["file_unique_id"]

            # Save immediately to DB channel
            file_ch_res = await TelegramUploader.copy_to_file_channel(
                main_message_id=main_msg_id,
                file_id=file_id,
                video_file_path=video_path
            )
            file_id = file_ch_res.get("file_id") or file_id

            now = datetime.now(timezone.utc)
            settings = get_settings()
            archive_due = now + timedelta(hours=settings.DELETE_AFTER_HOURS)

            # 5. Mark ARCHIVE_PENDING
            await EpisodeRepository.update_status(
                episode.id,
                status=EpisodeStatus.ARCHIVE_PENDING,
                telegram_main_message_id=main_msg_id,
                telegram_file_id=file_id or episode.telegram_file_id,
                telegram_file_unique_id=file_unique_id or episode.telegram_file_unique_id,
                uploaded_at=now,
                archive_due_at=archive_due
            )

            logger.info(f"Episode {episode.id} successfully uploaded to MAIN channel. Archive due at: {archive_due}")
            await TelegramUploader.send_log(
                f"✅ NEW EPISODE UPLOADED\n📺 {episode.show_name}\n🎬 Episode {episode.episode_number}\n📅 {episode.episode_date}"
            )
        except Exception as e:
            error_msg = f"Failed uploading episode {episode.id}: {e}"
            logger.error(error_msg, exc_info=True)
            await EpisodeRepository.record_error(episode.id, str(e), status=EpisodeStatus.FAILED)
            await TelegramUploader.send_log(f"❌ UPLOAD ERROR\n📺 {episode.show_name}\nReason: {e}")
        finally:
            # Clean up local downloaded files
            if video_path:
                cleanup_file(video_path)
            if poster_path:
                cleanup_file(poster_path)

    async def recover_stuck_episodes(self):
        """On startup, reset episodes stuck in transient downloading/uploading states back to DETECTED."""
        stuck_downloading = await EpisodeRepository.get_by_status(EpisodeStatus.DOWNLOADING)
        stuck_uploading = await EpisodeRepository.get_by_status(EpisodeStatus.UPLOADING)

        for ep in stuck_downloading + stuck_uploading:
            logger.info(f"Recovering stuck episode {ep.id} (was in {ep.status.value}). Resetting to DETECTED.")
            await EpisodeRepository.update_status(ep.id, EpisodeStatus.DETECTED)
