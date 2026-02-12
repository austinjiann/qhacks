import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger("image_search")

IMAGE_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/png,image/jpeg,image/*,*/*;q=0.8",
}


async def search_and_fetch_image(query: str) -> Optional[bytes]:
    """Search DuckDuckGo Images for `query` and return the first usable image as bytes.

    Returns None if search fails or no image could be fetched.
    """
    try:
        from duckduckgo_search import DDGS

        results = await asyncio.to_thread(
            lambda: DDGS().images(query, max_results=5)
        )
        if not results:
            logger.warning(f"[image_search] No results for: {query}")
            return None

        # Try the top results until one downloads successfully
        for result in results:
            url = result.get("image")
            if not url:
                continue
            logger.info(f"[image_search] Trying: {url[:100]}")
            image_bytes = await _fetch_image(url)
            if image_bytes and len(image_bytes) > 5000:  # skip tiny/broken images
                logger.info(f"[image_search] Got image ({len(image_bytes)} bytes)")
                return image_bytes

        logger.warning(f"[image_search] All results failed for: {query}")
        return None
    except Exception as e:
        logger.error(f"[image_search] Search failed: {e}")
        return None


async def _fetch_image(url: str) -> Optional[bytes]:
    """Fetch image bytes from a URL with timeout."""
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(headers=IMAGE_REQUEST_HEADERS, connector=connector) as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10),
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    return None
                return await response.read()
    except Exception:
        return None
