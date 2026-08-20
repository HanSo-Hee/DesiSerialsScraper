import asyncio
import logging
import random
from typing import Optional
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Apple-iPhone7C2/1202.68; U; CPU OS 9_3_2 like Mac OS X; en_US) AppleWebKit/601.1.46 (KHTML, like Gecko) Mobile/13F69"
]

REFERERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    "https://t.co/",
    "https://www.facebook.com/"
]


def get_random_headers(referer: Optional[str] = None) -> dict:
    ref = referer or random.choice(REFERERS)
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": ref,
        "Sec-Ch-Ua": '"Chromium";v="123", "Not:A-Brand";v="8", "Google Chrome";v="123"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive"
    }


class ScraperClient:
    def __init__(self, request_delay: float = 1.5, timeout_seconds: int = 30):
        self.request_delay = request_delay
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            connector = aiohttp.TCPConnector(ssl=False, limit=0, ttl_dns_cache=300)
            self.session = aiohttp.ClientSession(
                headers=get_random_headers(),
                timeout=self.timeout,
                connector=connector
            )
        return self.session

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=12),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True
    )
    async def fetch_html(self, url: str, referer: Optional[str] = None) -> str:
        session = await self.get_session()
        logger.debug(f"Fetching HTML from URL: {url}")
        headers = get_random_headers(referer=referer)
        
        async with session.get(url, headers=headers) as response:
            if response.status in (403, 429, 503):
                logger.warning(f"Got HTTP {response.status} on {url}, retrying with jitter backoff...")
                await asyncio.sleep(random.uniform(1.0, 3.0))
                raise aiohttp.ClientResponseError(
                    request_info=response.request_info,
                    history=response.history,
                    status=response.status,
                    message=f"Cloudflare/CDN HTTP {response.status}"
                )
            response.raise_for_status()
            html = await response.text()
            if self.request_delay > 0:
                await asyncio.sleep(self.request_delay + random.uniform(0.2, 0.8))
            return html

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.info("Scraper HTTP session closed.")
