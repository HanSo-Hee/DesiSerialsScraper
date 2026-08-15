# github.com/MrAbhi2k3

import asyncio
import logging
from typing import Optional
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class ScraperClient:
    def __init__(self, request_delay: float = 1.0, timeout_seconds: int = 30):
        self.request_delay = request_delay
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=DEFAULT_HEADERS,
                timeout=self.timeout
            )
        return self.session

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True
    )
    async def fetch_html(self, url: str) -> str:
        session = await self.get_session()
        logger.debug(f"Fetching HTML from URL: {url}")
        async with session.get(url) as response:
            response.raise_for_status()
            html = await response.text()
            if self.request_delay > 0:
                await asyncio.sleep(self.request_delay)
            return html

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.info("Scraper HTTP session closed.")
