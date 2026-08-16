# github.com/MrAbhi2k3

import asyncio
import logging
from typing import Optional, List
from app.config import get_settings
from app.scheduler.jobs import scrape_job, archive_job, retry_job, cleanup_job

logger = logging.getLogger(__name__)


class SchedulerManager:
    tasks: List[asyncio.Task] = []
    running: bool = False

    @classmethod
    async def _run_interval_job(cls, job_func, interval_seconds: int, name: str):
        while cls.running:
            try:
                await job_func()
            except Exception as e:
                logger.error(f"Error in background task {name}: {e}")
            await asyncio.sleep(interval_seconds)

    @classmethod
    def initialize(cls):
        settings = get_settings()
        cls.running = True
        cls.tasks = [
            asyncio.create_task(cls._run_interval_job(scrape_job, settings.SCRAPE_INTERVAL, "scrape_job")),
            asyncio.create_task(cls._run_interval_job(archive_job, 60, "archive_job")),
            asyncio.create_task(cls._run_interval_job(retry_job, 300, "retry_job")),
            asyncio.create_task(cls._run_interval_job(cleanup_job, 1800, "cleanup_job"))
        ]
        logger.info("Native asyncio background loop scheduler started successfully.")

    @classmethod
    def shutdown(cls):
        cls.running = False
        for task in cls.tasks:
            task.cancel()
        cls.tasks.clear()
        logger.info("Asyncio background loop scheduler shut down.")
