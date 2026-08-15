# github.com/MrAbhi2k3

import logging
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import get_settings
from app.scheduler.jobs import scrape_job, archive_job, retry_job, cleanup_job

logger = logging.getLogger(__name__)


class SchedulerManager:
    scheduler: Optional[AsyncIOScheduler] = None

    @classmethod
    def initialize(cls) -> AsyncIOScheduler:
        settings = get_settings()
        cls.scheduler = AsyncIOScheduler(timezone=settings.TIMEZONE)

        # Scrape job: default every 5 minutes
        cls.scheduler.add_job(
            scrape_job,
            "interval",
            seconds=settings.SCRAPE_INTERVAL,
            id="scrape_job",
            replace_existing=True
        )

        # Archive check job: every 1 minute
        cls.scheduler.add_job(
            archive_job,
            "interval",
            minutes=1,
            id="archive_job",
            replace_existing=True
        )

        # Retry job: every 5 minutes
        cls.scheduler.add_job(
            retry_job,
            "interval",
            minutes=5,
            id="retry_job",
            replace_existing=True
        )

        # Cleanup job: every 30 minutes
        cls.scheduler.add_job(
            cleanup_job,
            "interval",
            minutes=30,
            id="cleanup_job",
            replace_existing=True
        )

        cls.scheduler.start()
        logger.info("APScheduler started successfully with all configured jobs.")
        return cls.scheduler

    @classmethod
    def shutdown(cls):
        if cls.scheduler and cls.scheduler.running:
            cls.scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down.")
