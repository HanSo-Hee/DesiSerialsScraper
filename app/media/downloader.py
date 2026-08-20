import os
import asyncio
import logging
import subprocess
from typing import Optional, Any
from urllib.parse import urljoin
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
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError, ValueError)),
        reraise=True
    )
    async def download_file(self, url: str, custom_filename: Optional[str] = None, status_message: Optional[Any] = None) -> str:
        filename = custom_filename or get_filename_from_url(url)
        filepath = get_safe_filepath(self.download_dir, filename)

        logger.info(f"Downloading from {url} to {filepath}")

        # Check if URL is an HLS m3u8 stream
        if ".m3u8" in url.lower():
            return await self._download_hls_stream(url, filepath, status_message)

        # Standard file download (e.g. poster image or direct mp4)
        return await self._download_direct_http(url, filepath, filename, status_message)

    async def _download_hls_stream(self, url: str, filepath: str, status_message: Optional[Any] = None) -> str:
        """Downloads an HLS .m3u8 stream using ffmpeg or segment fetching."""
        # First try ffmpeg if available
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        if "token=" in url:
            try:
                import base64
                tok = url.split("token=")[-1]
                dec = base64.b64decode(tok + "==").decode("utf-8", errors="ignore")
                if "|" in dec:
                    ua = dec.split("|")[0]
            except Exception:
                pass

        ffmpeg_bin = self._find_ffmpeg()
        if ffmpeg_bin:
            try:
                logger.info(f"Using ffmpeg for HLS download: {filepath}")
                cmd = [
                    ffmpeg_bin, "-y",
                    "-headers", f"User-Agent: {ua}\r\nReferer: https://flow.tvlogy.to/\r\nOrigin: https://flow.tvlogy.to\r\n",
                    "-i", url,
                    "-c", "copy",
                    "-bsf:a", "aac_adtstoasc",
                    filepath
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                _, stderr = await proc.communicate()
                if proc.returncode == 0 and os.path.exists(filepath):
                    file_size = os.path.getsize(filepath)
                    if file_size >= 100 * 1024:
                        logger.info(f"ffmpeg download complete: {filepath} ({file_size} bytes)")
                        return filepath
                logger.warning(f"ffmpeg returned non-zero code {proc.returncode} or output too small: {stderr.decode()[-300:]}")
            except Exception as e:
                logger.warning(f"ffmpeg execution failed: {e}. Falling back to Python HLS segment downloader...")

        # Fallback to direct Python HLS segment downloader
        return await self._download_hls_python(url, filepath, status_message)

    async def _download_hls_python(self, master_url: str, filepath: str, status_message: Optional[Any] = None) -> str:
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        if "token=" in master_url:
            try:
                import base64
                tok = master_url.split("token=")[-1]
                dec = base64.b64decode(tok + "==").decode("utf-8", errors="ignore")
                if "|" in dec:
                    ua = dec.split("|")[0]
            except Exception:
                pass

        headers = {
            "User-Agent": ua,
            "Referer": "https://flow.tvlogy.to/",
            "Origin": "https://flow.tvlogy.to"
        }
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
            # 1. Fetch master playlist
            async with session.get(master_url) as r:
                r.raise_for_status()
                master_text = await r.text()

            # Parse variant stream or segments
            lines = [line.strip() for line in master_text.splitlines() if line.strip() and not line.startswith('#')]
            if not lines:
                raise ValueError("Empty or invalid M3U8 playlist")

            playlist_url = master_url
            if any(l.endswith('.m3u8') for l in lines):
                playlist_url = urljoin(master_url, lines[0])
                async with session.get(playlist_url) as r:
                    r.raise_for_status()
                    playlist_text = await r.text()
                lines = [line.strip() for line in playlist_text.splitlines() if line.strip() and not line.startswith('#')]

            # 2. Download segments sequentially into the output file
            downloaded_bytes = 0
            total_segments = len(lines)
            logger.info(f"Downloading {total_segments} HLS segments to {filepath}...")

            with open(filepath, "wb") as f:
                for idx, seg_rel in enumerate(lines):
                    seg_url = urljoin(playlist_url, seg_rel)
                    try:
                        async with session.get(seg_url) as resp:
                            if resp.status == 200:
                                chunk = await resp.read()
                                f.write(chunk)
                                downloaded_bytes += len(chunk)
                    except Exception as se:
                        logger.warning(f"Error fetching segment {idx}/{total_segments}: {se}")

            file_size = os.path.getsize(filepath)
            if file_size < 100 * 1024:
                cleanup_file(filepath)
                raise ValueError(f"HLS downloaded video file too small ({file_size} bytes). Stream may be offline or protected.")

            logger.info(f"HLS Python download complete: {filepath} ({file_size} bytes)")
            return filepath

    async def _download_direct_http(self, url: str, filepath: str, filename: str, status_message: Optional[Any] = None) -> str:
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
                        async for chunk in response.content.iter_chunked(8 * 1024 * 1024):
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

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        for path in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"]:
            try:
                res = subprocess.run([path, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res.returncode == 0:
                    return path
            except Exception:
                pass
        return None
