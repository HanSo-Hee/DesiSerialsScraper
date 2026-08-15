# github.com/MrAbhi2k3

import logging
from app.database.models import EpisodeStatus
from app.database.repositories import EpisodeRepository
from app.services.episode_service import EpisodeService

logger = logging.getLogger(__name__)


class RetryService:
    @classmethod
    async def retry_failed_episodes(cls, max_retries: int = 3) -> int:
        """Finds failed episodes and resets them to DETECTED for retry."""
        failed_list = await EpisodeRepository.get_failed_episodes(max_retries=max_retries)
        if not failed_list:
            logger.info("No failed episodes requiring retry.")
            return 0

        logger.info(f"Retrying {len(failed_list)} failed episodes...")
        episode_service = EpisodeService()

        count = 0
        for ep in failed_list:
            logger.info(f"Resetting failed episode {ep.id} (Retry count: {ep.retry_count}) to DETECTED.")
            await EpisodeRepository.update_status(ep.id, status=EpisodeStatus.DETECTED)
            await episode_service.process_single_episode(ep)
            count += 1

        return count
