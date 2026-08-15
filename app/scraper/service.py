# github.com/MrAbhi2k3

import logging
from typing import List, Optional
from app.config import get_settings
from app.database.models import EpisodeModel, EpisodeStatus
from app.database.repositories import EpisodeRepository, ShowRepository
from app.scraper.extractor import ScraperExtractor
from app.scraper.models import ScrapedEpisode

logger = logging.getLogger(__name__)


class ScraperService:
    def __init__(self, extractor: Optional[ScraperExtractor] = None):
        self.extractor = extractor or ScraperExtractor()

    async def scan_and_ingest(self) -> List[EpisodeModel]:
        settings = get_settings()
        sources = [settings.SOURCE_URL]
        alt_source = "https://www.desi-serials.to/latest-episodes/"
        if alt_source not in sources:
            sources.append(alt_source)

        new_episodes: List[EpisodeModel] = []
        for src_url in sources:
            try:
                scraped_list: List[ScrapedEpisode] = await self.extractor.extract_latest_episodes(src_url)
                for item in scraped_list:
                    try:
                        existing = await EpisodeRepository.find_duplicate(
                            source_url=item.episode_url,
                            canonical_id=item.canonical_id
                        )
                        if existing:
                            logger.debug(f"Skipping existing episode: {item.show_name} Ep {item.episode_number}")
                            continue

                        show = await ShowRepository.get_or_create(
                            name=item.show_name,
                            normalized_name=item.normalized_show_name,
                            poster_url=item.poster_url
                        )

                        ep_model = EpisodeModel(
                            show_name=item.show_name,
                            normalized_show_name=item.normalized_show_name,
                            episode_number=item.episode_number,
                            episode_title=item.episode_title,
                            episode_date=item.episode_date,
                            source_url=item.episode_url,
                            poster_url=item.poster_url or show.poster_url,
                            media_url=item.media_url,
                            source=item.source,
                            canonical_id=item.canonical_id,
                            status=EpisodeStatus.DETECTED
                        )

                        inserted = await EpisodeRepository.insert(ep_model)
                        new_episodes.append(inserted)
                        logger.info(f"Ingested new episode ID {inserted.id}: {inserted.show_name} - Ep {inserted.episode_number}")
                    except Exception as e:
                        logger.error(f"Error ingesting episode {item.episode_url}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Error scanning source {src_url}: {e}")

        return new_episodes

    async def close(self):
        await self.extractor.close()
