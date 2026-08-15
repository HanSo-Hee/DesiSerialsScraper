# github.com/MrAbhi2k3

import re
import logging
from typing import List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.scraper.models import ScrapedEpisode

logger = logging.getLogger(__name__)


class ScraperParser:
    @staticmethod
    def parse_latest_episodes(html_content: str, base_url: str) -> List[dict]:
        """Extracts listing items (title, url, poster, date snippet) from listing/home page HTML."""
        soup = BeautifulSoup(html_content, "lxml" if "lxml" in BeautifulSoup.__dict__ else "html.parser")
        items = []

        # Target article, post, or entry tags
        elements = soup.find_all(["article", "div", "li"], class_=re.compile(re.escape("post") + r"|" + re.escape("entry") + r"|" + re.escape("item") + r"|" + re.escape("episode"), re.I))
        if not elements:
            # Fallback to all links inside main content if specific post containers aren't found
            elements = soup.find_all("a", href=True)

        for el in elements:
            try:
                a_tag = el.find("a", href=True) if el.name != "a" else el
                if not a_tag:
                    continue

                url = urljoin(base_url, a_tag["href"])
                # Exclude static/nav links
                if not url or any(x in url for x in ["/category/", "/tag/", "/contact", "/privacy", "/about", "#"]):
                    continue

                title = a_tag.get_text(strip=True) or a_tag.get("title", "")
                if not title and el.name != "a":
                    title = el.get_text(strip=True)

                if not title or len(title) < 4:
                    continue

                img_tag = el.find("img")
                poster_url = None
                if img_tag:
                    poster_url = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-lazy-src")
                    if poster_url:
                        poster_url = urljoin(base_url, poster_url)

                items.append({
                    "title": title,
                    "url": url,
                    "poster_url": poster_url
                })
            except Exception as e:
                logger.debug(f"Error parsing listing element: {e}")
                continue

        # Deduplicate listing items by URL
        unique_items = {}
        for item in items:
            if item["url"] not in unique_items:
                unique_items[item["url"]] = item

        return list(unique_items.values())

    @classmethod
    def parse_episode_page(cls, html_content: str, page_url: str, fallback_poster: Optional[str] = None) -> Optional[ScrapedEpisode]:
        """Parses individual episode page content to extract show name, episode number, date, media URL, poster."""
        soup = BeautifulSoup(html_content, "lxml" if "lxml" in BeautifulSoup.__dict__ else "html.parser")
        
        # 1. Page title / Main header
        h1 = soup.find(["h1", "h2"], class_=re.compile(r"title|entry", re.I)) or soup.find("h1")
        page_title = h1.get_text(strip=True) if h1 else ""
        if not page_title and soup.title:
            page_title = soup.title.get_text(strip=True)

        if not page_title:
            logger.warning(f"Could not extract title for page: {page_url}")
            return None

        show_name = cls.extract_show_name(page_title)
        episode_number = cls.extract_episode_number(page_title)
        episode_date = cls.extract_episode_date(page_title, html_content)
        poster_url = cls.extract_poster(soup, page_url) or fallback_poster
        media_url = cls.extract_media_url(soup, page_url)

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
        """Extract clean show name from episode title."""
        cleaned = re.sub(r'(?i)\b(episode|ep|full episode|watch online|hd|720p|1080p|mp4|part|\d{1,2}(st|nd|rd|th)?\s+[a-z]+\s+\d{4})\b.*$', '', title)
        cleaned = re.split(r'[-–—|:]', cleaned)[0]
        cleaned = cleaned.strip(" -_–—|:")
        return cleaned if cleaned else title

    @staticmethod
    def extract_episode_number(title: str) -> str:
        """Extract episode number from title (e.g. Episode 2105 -> 2105)."""
        match = re.search(r'(?i)\b(?:episode|ep)\s*#?\s*(\d+)', title)
        if match:
            return match.group(1)
        
        # Standalone numeric search if preceded/followed by boundaries
        match = re.search(r'\b(\d{3,5})\b', title)
        if match:
            return match.group(1)
        return "1"

    @staticmethod
    def extract_episode_date(title: str, html_content: str) -> str:
        """Extract date from title or HTML body."""
        # e.g., 14th August 2026 or 14 August 2026
        match = re.search(r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})\b', title, re.I)
        if match:
            return match.group(1)

        # e.g., 2026-08-14 or 14-08-2026
        match = re.search(r'\b(\d{2,4}[-/\.]\d{1,2}[-/\.]\d{2,4})\b', title)
        if match:
            return match.group(1)

        # Look in page HTML
        match = re.search(r'\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b', html_content, re.I)
        if match:
            return match.group(1)

        return "Today"

    @staticmethod
    def extract_poster(soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract poster image from soup HTML."""
        # Check og:image meta tag first
        meta_og = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
        if meta_og and meta_og.get("content"):
            return urljoin(base_url, meta_og["content"])

        # Check content images
        img = soup.find("img", class_=re.compile(r"poster|thumb|entry|wp-post-image", re.I))
        if img:
            src = img.get("src") or img.get("data-src")
            if src:
                return urljoin(base_url, src)

        return None

    @staticmethod
    def extract_media_url(soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract direct authorized media URL (video tag, direct mp4/m3u8 link, or stream iframe player)."""
        # Look for HTML5 video source tag
        video_source = soup.find("source", src=True)
        if video_source:
            return urljoin(base_url, video_source["src"])

        video_tag = soup.find("video", src=True)
        if video_tag:
            return urljoin(base_url, video_tag["src"])

        # Look for direct links to mp4/mkv/m3u8 files
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if re.search(r'\.(mp4|mkv|m3u8|avi)(\?.*)?$', href, re.I):
                return urljoin(base_url, href)

        # Look for stream iframe players
        for iframe in soup.find_all("iframe", src=True):
            iframe_src = iframe["src"]
            if any(k in iframe_src.lower() for k in ["stream", "embed", "player", "tamilembed", "vkprime", "videoman", ".mp4", ".m3u8"]):
                return urljoin(base_url, iframe_src)

        return None
