# github.com/MrAbhi2k3

import os
import asyncio
import logging
from typing import Optional, Any
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import get_settings
from app.media.cleanup import cleanup_file
from app.media.validator import get_safe_filepath, get_filename_from_url

logger = logging.getLogger(__name__)


class MediaDownloader:
    def __init__(self, download_dir: Optional[str] = None, timeout: Optional[int] = None):
        settings = get_settings()
        self.download_dir = download_dir or settings.DOWNLOAD_DIR
        self.timeout_seconds = timeout or settings.DOWNLOAD_TIMEOUT
        os.makedirs(self.download_dir, exist_ok=True)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=3, max=15),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True
    )
    async def download_file(self, url: str, custom_filename: Optional[str] = None, status_message: Optional[Any] = None) -> str:
        """Stream downloads video or poster file to prevent loading into RAM."""
        filename = custom_filename or get_filename_from_url(url)
        filepath = get_safe_filepath(self.download_dir, filename)

        logger.info(f"Downloading from {url} to {filepath}")
        timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector, read_bufsize=1024*1024) as session:
                async with session.get(url) as response:
                    if response.status not in (200, 404):
                        response.raise_for_status()
                    
                    total_size = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    
                    tracker = None
                    if status_message and total_size > 0:
                        from app.telegram.progress import ProgressTracker
                        tracker = ProgressTracker(status_message, action_name="Downloading Media")

                    with open(filepath, "wb") as f:
                        async for chunk in response.content.iter_chunked(8 * 1024 * 1024):  # 8MB chunk buffer
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if tracker and total_size > 0:
                                    await tracker.update(downloaded, total_size)
                    
                    file_size = os.path.getsize(filepath)
                    if not filename.startswith("poster_") and file_size < 100 * 1024:
                        cleanup_file(filepath)
                        raise ValueError(f"Downloaded video file too small ({file_size} bytes). Direct video stream link invalid or protected.")

                    if filename.startswith("poster_"):
                        try:
                            from PIL import Image
                            jpg_path = filepath.rsplit(".", 1)[0] + ".jpg"
                            with Image.open(filepath) as img:
                                img.convert("RGB").save(jpg_path, "JPEG")
                            if jpg_path != filepath and os.path.exists(filepath):
                                os.remove(filepath)
                            filepath = jpg_path
                        except Exception as pe:
                            logger.warning(f"Poster image JPEG conversion warning: {pe}")

                    logger.info(f"Download complete: {filepath} ({file_size} bytes)")
                    return filepath
        except Exception as e:
            cleanup_file(filepath)
            logger.error(f"Download failed for {url}: {e}")
            raise
