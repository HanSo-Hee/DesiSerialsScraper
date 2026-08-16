import re
import logging
import warnings
from typing import List, Optional
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning
from urllib.parse import urljoin
from app.scraper.models import ScrapedEpisode

warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

logger = logging.getLogger(__name__)

DESI_SERIALS_EPISODE_URL_RE = re.compile(
    r'https?://(?:www\.)?desi-serials\.to/[a-z0-9\-]+-episode-[a-z0-9\-]+/\d+/',
    re.I
)

NAV_SKIP_KEYWORDS = [
    "/category/", "/tag/", "/contact", "/privacy", "/about",
    "/author/", "#", "?s=", "?p=", "/page/", "/feed",
    "tumblr.com", "facebook.com", "twitter.com", "whatsapp.com",
    "terms-of-use", "content-policy",
]


class ScraperParser:
    @staticmethod
    def _clean_url(url: str) -> str:
        return re.sub(r'^httpss://', 'https://', url, flags=re.I)

    @staticmethod
    def parse_latest_episodes(html_content: str, base_url: str) -> List[dict]:
        soup = BeautifulSoup(html_content, "lxml")
        items = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            href = ScraperParser._clean_url(urljoin(base_url, a["href"]))
            if not DESI_SERIALS_EPISODE_URL_RE.match(href):
                continue
            if href in seen_urls:
                continue
            if any(skip in href.lower() for skip in NAV_SKIP_KEYWORDS):
                continue
            seen_urls.add(href)

            img_tag = a.find("img") or (a.parent and a.parent.find("img"))
            poster_url = None
            if img_tag:
                raw = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
                if raw:
                    poster_url = urljoin(base_url, raw)

            items.append({"url": href, "poster_url": poster_url})

        logger.info(f"Found {len(items)} real episode links after filtering.")
        return items

    @classmethod
    def parse_episode_page(cls, html_content: str, page_url: str, fallback_poster: Optional[str] = None) -> Optional[ScrapedEpisode]:
        soup = BeautifulSoup(html_content, "lxml")

        h1 = soup.find("h1", class_=re.compile(r"title|entry", re.I)) or soup.find("h1")
        page_title = h1.get_text(strip=True) if h1 else ""
        if not page_title and soup.title:
            page_title = soup.title.get_text(strip=True).split("|")[0].strip()

        if not page_title:
            logger.warning(f"Could not extract title for page: {page_url}")
            return None

        show_name = cls.extract_show_name(page_title)
        if not show_name or len(show_name) < 3:
            logger.warning(f"Skipping page with invalid show name from title: {page_title[:60]}")
            return None

        episode_number = cls.extract_episode_number(page_title)
        episode_date = cls.extract_episode_date(page_title, html_content)
        poster_url = cls.extract_poster(soup, page_url) or fallback_poster
        media_url = cls.extract_media_url(soup, page_url)

        if media_url:
            media_url = cls._clean_url(media_url)

        return ScrapedEpisode(
            show_name=show_name,
            episode_number=episode_number,
            episode_title=page_title,
            episode_date=episode_date,
            episode_url=page_url,
            poster_url=poster_url,
            media_url=media_url
        )

    @staticmethod
    def extract_show_name(title: str) -> str:
        cleaned = re.sub(
            r'(?i)\s*[-–—|]\s*(?:episode|ep\.?\s*\d+|full episode|watch online|hd|720p|1080p).*$',
            '', title
        )
        cleaned = re.sub(
            r'(?i)\s+(?:episode|ep\.?\s*\d+|\d{1,2}(?:st|nd|rd|th)?\s+\w+\s+\d{4}).*$',
            '', cleaned
        )
        cleaned = cleaned.strip(" -_–—|:")
        return cleaned if cleaned else title

    @staticmethod
    def extract_episode_number(title: str) -> str:
        match = re.search(r'(?i)\b(?:episode|ep)\.?\s*#?\s*(\d+)', title)
        if match:
            return match.group(1)
        for m in re.finditer(r'\b(\d{3,5})\b', title):
            val = m.group(1)
            if not re.search(r'\b' + re.escape(val) + r'\b', title, re.I) or int(val) < 2000 or int(val) > 2100:
                return val
        return "1"

    @staticmethod
    def extract_episode_date(title: str, html_content: str) -> str:
        match = re.search(
            r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b',
            title, re.I
        )
        if match:
            return match.group(1)
        match = re.search(
            r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',
            html_content, re.I
        )
        if match:
            return match.group(1)
        return "Today"

    @staticmethod
    def extract_poster(soup: BeautifulSoup, base_url: str) -> Optional[str]:
        meta_og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if meta_og and meta_og.get("content"):
            return urljoin(base_url, meta_og["content"])
        img = soup.find("img", class_=re.compile(r"poster|thumb|entry|wp-post-image", re.I))
        if img:
            src = img.get("src") or img.get("data-src")
            if src:
                return urljoin(base_url, src)
        return None

    @staticmethod
    def extract_media_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
        video_source = soup.find("source", src=True)
        if video_source:
            return urljoin(base_url, video_source["src"])
        video_tag = soup.find("video", src=True)
        if video_tag:
            return urljoin(base_url, video_tag["src"])
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r'\.(mp4|mkv|m3u8|avi)(\?.*)?$', href, re.I):
                return urljoin(base_url, href)
        for iframe in soup.find_all("iframe", src=True):
            iframe_src = iframe["src"]
            if any(k in iframe_src.lower() for k in ["stream", "embed", "player", "tamilembed", "tvlogy", "tvarticles", "vidd", ".mp4", ".m3u8"]):
                res_url = re.sub(r'^httpss://', 'https://', urljoin(base_url, iframe_src), flags=re.I)
                return res_url
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if any(k in href.lower() for k in ["tvarticles", "tvlogy", "vidd.php", "embed", "stream"]):
                res_url = re.sub(r'^httpss://', 'https://', urljoin(base_url, href), flags=re.I)
                return res_url
        return None
