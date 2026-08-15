# github.com/MrAbhi2k3

import logging
from app.database.repositories import SettingsRepository
from app.services.episode_service import EpisodeService
from app.services.archive_service import ArchiveService
from app.services.retry_service import RetryService
from app.media.cleanup import cleanup_directory

logger = logging.getLogger(__name__)


async def scrape_job():
    try:
        enabled = await SettingsRepository.get_setting("scraper_enabled", True)
        if not enabled:
            logger.debug("Scraper is currently disabled in settings.")
            return

        service = EpisodeService()
        await service.run_scraper_pipeline()
    except Exception as e:
        logger.error(f"Error executing scrape_job: {e}", exc_info=True)


async def archive_job():
    try:
        await ArchiveService.process_due_archives()
    except Exception as e:
        logger.error(f"Error executing archive_job: {e}", exc_info=True)


async def retry_job():
    try:
        await RetryService.retry_failed_episodes()
    except Exception as e:
        logger.error(f"Error executing retry_job: {e}", exc_info=True)


async def cleanup_job():
    try:
        removed = cleanup_directory()
        logger.info(f"Routine cleanup job completed. Removed {removed} files.")
    except Exception as e:
        logger.error(f"Error executing cleanup_job: {e}", exc_info=True)
