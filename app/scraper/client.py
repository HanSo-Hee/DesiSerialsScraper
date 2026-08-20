import asyncio
import logging
import random
from typing import Optional
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
]


def get_random_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Sec-Ch-Ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }


class ScraperClient:
    def __init__(self, request_delay: float = 1.0, timeout_seconds: int = 30):
        self.request_delay = request_delay
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers=get_random_headers(),
                timeout=self.timeout
            )
        return self.session

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True
    )
    async def fetch_html(self, url: str) -> str:
        session = await self.get_session()
        logger.debug(f"Fetching HTML from URL: {url}")
        async with session.get(url, headers=get_random_headers()) as response:
            if response.status == 403:
                logger.warning(f"Got 403 Forbidden on {url}, retrying with dynamic headers...")
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message="Cloudflare 403 Forbidden"
                )
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
