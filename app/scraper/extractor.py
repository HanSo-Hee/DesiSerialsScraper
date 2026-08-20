import asyncio
import logging
from typing import AsyncIterator, List, Optional
from app.scraper.client import ScraperClient
from app.scraper.models import ScrapedEpisode
from app.scraper.parser import ScraperParser

logger = logging.getLogger(__name__)


class ScraperExtractor:
    def __init__(self, client: Optional[ScraperClient] = None):
        self.client = client or ScraperClient()

    async def iter_latest_episodes(self, source_url: str, limit: int = 25) -> AsyncIterator[ScrapedEpisode]:
        logger.info(f"Scanning source site: {source_url}")
        try:
            home_html = await self.client.fetch_html(source_url)
        except Exception as e:
            logger.error(f"Failed to fetch homepage {source_url}: {e}")
            await self.client.close()
            return

        listings = ScraperParser.parse_latest_episodes(home_html, source_url)
        logger.info(f"Found {len(listings)} episode links. Will process one by one.")

        for item in listings[:limit]:
            page_url = item["url"]
            try:
                page_html = await self.client.fetch_html(page_url)
                episode = ScraperParser.parse_episode_page(
                    html_content=page_html,
                    page_url=page_url,
                    fallback_poster=item.get("poster_url")
                )
                if episode:
                    logger.info(f"Extracted: {episode.show_name} - Ep {episode.episode_number} ({episode.episode_date})")
                    yield episode
                await asyncio.sleep(2.5)
            except Exception as e:
                logger.warning(f"Error parsing episode page {page_url}: {e}")
                continue

        await self.client.close()

    async def close(self):
        await self.client.close()
