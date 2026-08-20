import asyncio
import logging
from datetime import datetime, timezone
from typing import List
from app.scheduler.jobs import scrape_job, archive_job, retry_job, cleanup_job

logger = logging.getLogger(__name__)

PEAK_HOURS_IST = {
    6, 7, 8,
    10, 11, 12, 13,
    18, 19, 20, 21, 22, 23,
}


def _ist_hour() -> int:
    utc_now = datetime.now(timezone.utc)
    ist_hour = (utc_now.hour + 5) % 24
    return ist_hour


def _scrape_interval_seconds(step_index: int) -> int:
    if _ist_hour() in PEAK_HOURS_IST:
        intervals = [30 * 60, 60 * 60, 90 * 60]
    else:
        intervals = [60 * 60, 120 * 60, 180 * 60]
    return intervals[min(step_index, len(intervals) - 1)]


class SchedulerManager:
    tasks: List[asyncio.Task] = []
    running: bool = False

    @classmethod
    async def _run_dynamic_scrape_job(cls):
        step_index = 0
        while cls.running:
            try:
                new_count = await scrape_job()
                if new_count and new_count > 0:
                    step_index = 0
                    logger.info(f"Scraped {new_count} new episodes. Resetting interval to peak schedule.")
                else:
                    if step_index < 2:
                        step_index += 1
            except Exception as e:
                logger.error(f"Error in dynamic scrape job: {e}")

            wait_secs = _scrape_interval_seconds(step_index)
            logger.info(f"Next scrape in {wait_secs // 60} min(s) [IST hour={_ist_hour()}, step={step_index}].")
            await asyncio.sleep(wait_secs)

    @classmethod
    async def _run_interval_job(cls, job_func, interval_seconds: int, name: str):
        await asyncio.sleep(interval_seconds)
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
            asyncio.create_task(cls._run_interval_job(archive_job, 3600, "archive_job")),
            asyncio.create_task(cls._run_interval_job(retry_job, 600, "retry_job")),
            asyncio.create_task(cls._run_interval_job(cleanup_job, 1800, "cleanup_job")),
        ]
        logger.info("Scheduler initialized with IST-aware TV schedule-based scraping intervals.")

    @classmethod
    def shutdown(cls):
        cls.running = False
        for task in cls.tasks:
            task.cancel()
        cls.tasks.clear()
        logger.info("Scheduler shut down.")
