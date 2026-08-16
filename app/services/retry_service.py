import re
import logging
from app.database.models import EpisodeStatus
from app.database.repositories import EpisodeRepository
from app.services.episode_service import EpisodeService

logger = logging.getLogger(__name__)

PERMANENT_FAIL_REASONS = ["Invalid URL scheme", "Stream could not be resolved"]


class RetryService:
    @classmethod
    async def retry_failed_episodes(cls, max_retries: int = 3) -> int:
        failed_list = await EpisodeRepository.get_failed_episodes(max_retries=max_retries)
        if not failed_list:
            return 0

        logger.info(f"Retrying {len(failed_list)} failed episodes...")
        episode_service = EpisodeService()
        count = 0

        for ep in failed_list:
            if ep.last_error and any(reason in ep.last_error for reason in PERMANENT_FAIL_REASONS):
                logger.warning(f"Skipping permanently failed episode {ep.id}: {ep.last_error}")
                continue

            if ep.media_url:
                clean_url = re.sub(r'^httpss://', 'https://', ep.media_url, flags=re.I)
                if not re.match(r'^https?://', clean_url, re.I):
                    logger.warning(f"Permanently invalid URL for {ep.id}, skipping retry.")
                    continue

            logger.info(f"Retrying episode {ep.id} ({ep.show_name}) - attempt {ep.retry_count + 1}/{max_retries}")
            await EpisodeRepository.update_status(ep.id, status=EpisodeStatus.DETECTED)
            await episode_service.process_single_episode(ep)
            count += 1

        return count
