import os
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Any

from app.config import get_settings
from app.database.models import EpisodeModel, EpisodeStatus
from app.database.repositories import EpisodeRepository, ShowRepository
from app.media.cleanup import cleanup_file
from app.media.downloader import MediaDownloader
from app.scraper.extractor import ScraperExtractor
from app.scraper.resolver import StreamResolver
from app.telegram.uploader import TelegramUploader

logger = logging.getLogger(__name__)


class EpisodeService:
    def __init__(self):
        self.downloader = MediaDownloader()

    async def run_scraper_pipeline(self) -> int:
        logger.info("Running automated scraper pipeline...")
        settings = get_settings()
        extractor = ScraperExtractor()
        scraped_list = await extractor.extract_latest_episodes(settings.SOURCE_URL, limit=25)

        new_episodes: List[EpisodeModel] = []
        for item in scraped_list:
            try:
                existing = await EpisodeRepository.find_duplicate(
                    source_url=item.episode_url,
                    canonical_id=item.canonical_id
                )
                if existing:
                    logger.debug(f"Skipping duplicate: {item.show_name} Ep {item.episode_number}")
                    continue

                show = await ShowRepository.get_or_create(
                    name=item.show_name,
                    normalized_name=item.normalized_show_name,
                    poster_url=item.poster_url
                )
                ep = EpisodeModel(
                    show_name=item.show_name,
                    normalized_show_name=item.normalized_show_name,
                    episode_number=item.episode_number,
                    episode_title=item.episode_title,
                    episode_date=item.episode_date,
                    source_url=item.episode_url,
                    poster_url=item.poster_url or show.poster_url,
                    media_url=item.media_url,
                    source=item.source,
                    canonical_id=item.canonical_id,
                    status=EpisodeStatus.DETECTED
                )
                inserted = await EpisodeRepository.insert(ep)
                new_episodes.append(inserted)
                logger.info(f"Queued: {inserted.show_name} Ep {inserted.episode_number}")
            except Exception as e:
                logger.error(f"Error ingesting {item.episode_url}: {e}")

        logger.info(f"Scraper pipeline complete. {len(new_episodes)} new episodes queued.")

        for ep in new_episodes:
            try:
                await self.process_single_episode(ep)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error processing {ep.id}: {e}")

        return len(new_episodes)

    async def process_detected_episodes(self):
        detected = await EpisodeRepository.get_by_status(EpisodeStatus.DETECTED)
        if not detected:
            return
        logger.info(f"Processing {len(detected)} DETECTED episodes...")
        for ep in detected:
            await self.process_single_episode(ep)
            await asyncio.sleep(2)

    async def process_single_episode(
        self,
        episode: EpisodeModel,
        status_message: Optional[Any] = None,
        reply_to_user_chat: Optional[int] = None
    ) -> Optional[EpisodeModel]:
        acquired = await EpisodeRepository.try_acquire_lock(
            episode.id,
            current_status=EpisodeStatus.DETECTED,
            target_status=EpisodeStatus.DOWNLOADING
        )
        if not acquired:
            logger.debug(f"Episode {episode.id} already being processed.")
            return None

        video_path: Optional[str] = None
        poster_path: Optional[str] = None

        try:
            if not episode.media_url:
                await EpisodeRepository.record_error(episode.id, "No media URL found on episode page.", status=EpisodeStatus.FAILED)
                return None

            clean_url = re.sub(r'^httpss?://', 'https://', episode.media_url, flags=re.I)
            if not re.match(r'^https?://', clean_url, re.I):
                await EpisodeRepository.record_error(episode.id, f"Invalid URL: {episode.media_url}", status=EpisodeStatus.FAILED)
                return None

            resolved_url = await StreamResolver.resolve_stream_url(clean_url)
            if not resolved_url:
                await EpisodeRepository.record_error(episode.id, "Stream could not be resolved.", status=EpisodeStatus.FAILED)
                return None

            safe_name = re.sub(r'[^\w\s-]', '', episode.show_name).strip().replace(' ', '_')
            filename = f"{safe_name}_Ep_{episode.episode_number}_[@tellyfun_official].mp4"

            video_path = await self.downloader.download_file(
                resolved_url,
                custom_filename=filename,
                status_message=status_message
            )

            if episode.poster_url:
                try:
                    poster_path = await self.downloader.download_file(
                        episode.poster_url,
                        custom_filename=f"poster_{episode.id}.jpg"
                    )
                except Exception as e:
                    logger.warning(f"Poster download failed for {episode.id}: {e}")

            if not video_path or not os.path.exists(video_path):
                await EpisodeRepository.record_error(episode.id, "Video file missing after download.", status=EpisodeStatus.FAILED)
                return None

            await EpisodeRepository.update_status(episode.id, EpisodeStatus.UPLOADING)

            upload_res = await TelegramUploader.upload_to_main_channel(
                episode=episode,
                video_file_path=video_path,
                poster_file_path=poster_path,
                status_message=status_message
            )

            main_msg_id = upload_res["message_id"]
            file_id = upload_res["file_id"]
            file_unique_id = upload_res["file_unique_id"]

            file_ch_res = await TelegramUploader.copy_to_file_channel(
                main_message_id=main_msg_id,
                file_id=file_id,
                video_file_path=video_path
            )
            file_id = file_ch_res.get("file_id") or file_id

            if reply_to_user_chat:
                await TelegramUploader.send_video_to_chat(
                    chat_id=reply_to_user_chat,
                    file_id=file_id,
                    episode=episode
                )

            now = datetime.now(timezone.utc)
            settings = get_settings()
            archive_due = now + timedelta(hours=settings.DELETE_AFTER_HOURS)

            await EpisodeRepository.update_status(
                episode.id,
                status=EpisodeStatus.ARCHIVE_PENDING,
                telegram_main_message_id=main_msg_id,
                telegram_file_id=file_id,
                telegram_file_unique_id=file_unique_id,
                uploaded_at=now,
                archive_due_at=archive_due
            )

            logger.info(f"Uploaded: {episode.show_name} Ep {episode.episode_number}")
            await TelegramUploader.send_log(
                f"✅ UPLOADED\n📺 {episode.show_name}\n🎬 Ep {episode.episode_number}\n📅 {episode.episode_date}"
            )

            updated = await EpisodeRepository.find_by_id(episode.id)
            return updated

        except Exception as e:
            logger.error(f"Failed processing episode {episode.id}: {e}", exc_info=True)
            await EpisodeRepository.record_error(episode.id, str(e), status=EpisodeStatus.FAILED)
            await TelegramUploader.send_log(f"❌ FAILED\n📺 {episode.show_name}\nReason: {e}")
            return None
        finally:
            if video_path:
                cleanup_file(video_path)
            if poster_path:
                cleanup_file(poster_path)

    async def recover_stuck_episodes(self):
        for status in [EpisodeStatus.DOWNLOADING, EpisodeStatus.UPLOADING]:
            stuck = await EpisodeRepository.get_by_status(status)
            for ep in stuck:
                logger.info(f"Recovering stuck episode {ep.id} ({status.value}) → DETECTED")
                await EpisodeRepository.update_status(ep.id, EpisodeStatus.DETECTED)
