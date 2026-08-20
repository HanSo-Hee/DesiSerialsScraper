import asyncio
import logging
from typing import List
from app.config import get_settings
from app.scheduler.jobs import scrape_job, archive_job, retry_job, cleanup_job

logger = logging.getLogger(__name__)


class SchedulerManager:
    tasks: List[asyncio.Task] = []
    running: bool = False

    @classmethod
    async def _run_dynamic_scrape_job(cls):
        step_index = 0
        intervals = [1 * 3600, 2 * 3600, 3 * 3600]
        while cls.running:
            try:
                new_count = await scrape_job()
                if new_count and new_count > 0:
                    step_index = 0
                else:
                    if step_index < len(intervals) - 1:
                        step_index += 1
            except Exception as e:
                logger.error(f"Error in dynamic scrape job: {e}")

            current_wait = intervals[step_index]
            logger.info(f"Next scrape scheduled in {current_wait // 3600} hour(s).")
            await asyncio.sleep(current_wait)

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
        cls.running = True
        cls.tasks = [
            asyncio.create_task(cls._run_dynamic_scrape_job()),
            asyncio.create_task(cls._run_interval_job(archive_job, 60, "archive_job")),
            asyncio.create_task(cls._run_interval_job(retry_job, 300, "retry_job")),
            asyncio.create_task(cls._run_interval_job(cleanup_job, 1800, "cleanup_job"))
        ]
        logger.info("Scheduler initialized with 1h->2h->3h dynamic backoff.")

    @classmethod
    def shutdown(cls):
        cls.running = False
        for task in cls.tasks:
            task.cancel()
        cls.tasks.clear()
        logger.info("Scheduler shut down.")
