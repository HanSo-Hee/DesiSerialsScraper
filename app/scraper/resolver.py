import re
import base64
import logging
from typing import Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.scraper.client import ScraperClient

logger = logging.getLogger(__name__)

DIRECT_STREAM_RE = re.compile(
    r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)(?:\?[^\s"\'<>]*)?',
    re.I
)
TVLOGY_CDN_RE = re.compile(
    r'https?://(?:hines|einsteinium|flow)\.tvlogy\.to/[^\s"\'<>]+',
    re.I
)
PLAYER_KEYWORDS = ["tvarticles", "vidd.php", "flow.tvlogy", "tvlogy", "tamilembed"]


def _p_unpack(source: str) -> Optional[str]:
    m = re.search(
        r"}\('(.*?)',(\d+),\d+,'(.*?)'\.split",
        source, re.S
    )
    if not m:
        return None
    payload, radix, keys = m.group(1), int(m.group(2)), m.group(3).split("|")

    def b_decode(n: int) -> str:
        chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if n == 0:
            return "0"
        res = ""
        while n > 0:
            res = chars[n % radix] + res
            n //= radix
        return res

    lookup = {b_decode(i): k if k else b_decode(i) for i, k in enumerate(keys)}
    return re.sub(r'\b(\w+)\b', lambda m: lookup.get(m.group(0), m.group(0)), payload)


def _extract_from_juicycodes_block(block: str) -> Optional[str]:
    frags = re.findall(r'"([A-Za-z0-9+/=]+)"', block)
    if not frags:
        return None
    combined = "".join(frags)
    pad = combined + "=" * (-len(combined) % 4)
    try:
        decoded_js = base64.b64decode(pad).decode("utf-8", errors="ignore")
    except Exception:
        return None

    unpacked = _p_unpack(decoded_js)
    js = unpacked or decoded_js

    m = re.search(r'["\']file["\']\s*:\s*["\']([^"\']+\.m3u8[^"\']*)["\']', js, re.I)
    if m:
        return m.group(1)

    matches = DIRECT_STREAM_RE.findall(js)
    if matches:
        return matches[0]

    return None


class StreamResolver:
    @staticmethod
    async def resolve_stream_url(url: str, timeout: int = 15) -> Optional[str]:
        url = re.sub(r'^httpss://', 'https://', url, flags=re.I)

        if not url.startswith(("http://", "https://")):
            logger.error(f"Invalid URL scheme: {url}")
            return None

        if any(x in url.lower() for x in [".m3u8", ".mp4"]):
            if "tvlogy.to" in url.lower() or "hines." in url.lower() or "einsteinium." in url.lower():
                return url
            return url

        logger.info(f"Resolving stream from: {url}")
        client = ScraperClient(timeout_seconds=timeout)

        try:
            html = await StreamResolver._fetch(client, url)
            if not html:
                return None

            result = StreamResolver._extract_stream(html, url)
            if result:
                return result

            soup = BeautifulSoup(html, "lxml")
            for iframe in soup.find_all("iframe", src=True):
                iframe_src = urljoin(url, iframe["src"])
                if not any(k in iframe_src.lower() for k in PLAYER_KEYWORDS):
                    continue

                referer = url
                inner_html = await StreamResolver._fetch(client, iframe_src, referer=referer)
                if not inner_html:
                    continue

                result = StreamResolver._extract_stream(inner_html, iframe_src)
                if result:
                    return result

                if "flow.tvlogy.to" in iframe_src.lower():
                    scripts = re.findall(r'<script[^>]*>(.*?)</script>', inner_html, re.S)
                    for block in scripts:
                        if "JuicyCodes" in block or "eval(function" in block:
                            stream = _extract_from_juicycodes_block(block)
                            if stream:
                                logger.info(f"Extracted stream via JuicyCodes decode: {stream[:80]}...")
                                return stream

            logger.warning(f"StreamResolver: could not extract stream from {url}")
            return None

        except Exception as e:
            logger.error(f"StreamResolver error for {url}: {e}")
            return None
        finally:
            await client.close()

    @staticmethod
    def _extract_stream(html: str, base_url: str) -> Optional[str]:
        cdn = TVLOGY_CDN_RE.findall(html)
        if cdn:
            for c in cdn:
                if ".m3u8" in c:
                    return c

        direct = DIRECT_STREAM_RE.findall(html)
        if direct:
            return direct[0]

        return None

    @staticmethod
    async def _fetch(client: ScraperClient, url: str, referer: Optional[str] = None) -> Optional[str]:
        try:
            if referer:
                import aiohttp
                extra_headers = {
                    "Referer": referer,
                    "Origin": re.sub(r'(https?://[^/]+).*', r'\1', referer),
                    "Sec-Fetch-Dest": "iframe",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "cross-site",
                }
                session = await client.get_session()
                async with session.get(url, headers=extra_headers) as r:
                    r.raise_for_status()
                    return await r.text()
            return await client.fetch_html(url)
        except Exception as e:
            logger.warning(f"Failed fetching {url}: {e}")
            return None
