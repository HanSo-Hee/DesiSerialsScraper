# github.com/MrAbhi2k3

import asyncio
import logging
from typing import Optional
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)


class StreamResolver:
    @staticmethod
    async def resolve_stream_url(url: str, timeout: int = 15) -> str:
        """Resolves raw media video stream (.mp4 / googlevideo) from dynamic embed players using Playwright."""
        if any(x in url.lower() for x in [".mp4", "googlevideo.com/videoplayback"]) and ".m3u8" not in url.lower():
            return url

        logger.info(f"Resolving dynamic stream from player embed: {url}")
        captured_stream: Optional[str] = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()

                def handle_request(req):
                    nonlocal captured_stream
                    r_url = req.url
                    if ("googlevideo.com/videoplayback" in r_url or ".m3u8" in r_url or r_url.endswith(".mp4")) and not captured_stream:
                        captured_stream = r_url
                        logger.info(f"StreamResolver successfully captured direct stream: {captured_stream[:120]}...")

                page.on("request", handle_request)

                try:
                    await page.goto(url, timeout=timeout * 1000)
                    await asyncio.sleep(2.5)

                    # Trigger playback across page frames
                    for frame in page.frames:
                        try:
                            await frame.evaluate("document.body.click()")
                        except Exception:
                            pass
                        try:
                            await frame.click("body", timeout=1000)
                        except Exception:
                            pass

                    for _ in range(12):
                        if captured_stream:
                            break
                        await asyncio.sleep(0.5)

                except Exception as e:
                    logger.warning(f"Playwright navigation warning for {url}: {e}")

                await browser.close()
        except Exception as e:
            logger.error(f"Playwright browser engine error during stream resolution: {e}")

        return captured_stream or url
