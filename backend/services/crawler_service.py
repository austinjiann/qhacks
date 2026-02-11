import asyncio
import random
from datetime import datetime, timezone

import aiohttp

from services.feed_service import FeedService
from services.firestore_service import FirestoreService
from services.youtube_service import YoutubeService
from utils.env import settings

SEARCH_QUERIES = [
    # Sports
    "nfl highlights today",
    "nba highlights tonight",
    "super bowl shorts",
    "march madness shorts",
    # Crypto / Finance
    "bitcoin price today shorts",
    "crypto news today shorts",
    "stock market today shorts",
    "tesla stock shorts",
    # Pop culture / Gen-Z
    "drake shorts",
    "elon musk shorts",
    "kanye shorts",
    "taylor swift shorts",
    "mr beast shorts",
    # Tech
    "ai news shorts",
    "tech news today shorts",
    "apple shorts",
    # Politics / Current events
    "trump shorts",
    "politics today shorts",
    "election news shorts",
]


class CrawlerService:
    def __init__(
        self,
        feed_service: FeedService,
        firestore_service: FirestoreService,
        youtube_service: YoutubeService,
    ) -> None:
        self.feed_service = feed_service
        self.firestore_service = firestore_service
        self.youtube_service = youtube_service
        self.api_key = settings.YOUTUBE_API_KEY

    async def search_youtube_shorts(self, query: str, max_results: int = 10) -> list[str]:
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "id",
            "q": query,
            "type": "video",
            "videoDuration": "short",
            "order": "relevance",
            "maxResults": max_results,
            "key": self.api_key,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
            video_ids = []
            for item in data.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid:
                    video_ids.append(vid)
            return video_ids
        except Exception as e:
            print(f"[crawler] YouTube search failed for '{query}': {e}")
            return []

    async def crawl_and_match(self, query: str | None = None, max_videos: int = 10) -> int:
        await self.firestore_service.update_crawler_state("running")
        try:
            search_query = query or random.choice(SEARCH_QUERIES)
            print(f"[crawler] Searching YouTube for: '{search_query}'")

            video_ids = await self.search_youtube_shorts(search_query, max_results=max_videos + 5)
            if not video_ids:
                await self.firestore_service.update_crawler_state("idle", 0)
                return 0

            existing_ids = set(await self.firestore_service.get_all_active_video_ids())
            new_ids = [vid for vid in video_ids if vid not in existing_ids][:max_videos]
            print(f"[crawler] Found {len(video_ids)} videos, {len(new_ids)} are new")

            if not new_ids:
                await self.firestore_service.update_crawler_state("idle", 0)
                return 0

            added = 0
            batch_size = 5
            for i in range(0, len(new_ids), batch_size):
                batch = new_ids[i : i + batch_size]
                results = await self.feed_service.get_feed(batch)
                for item in results:
                    video_id = item["youtube"]["video_id"]
                    await self.firestore_service.upsert_feed_item(video_id, {
                        "youtube": item["youtube"],
                        "kalshi": item["kalshi"],
                        "keywords": item.get("keywords", []),
                        "crawled_at": datetime.now(timezone.utc),
                        "source": "crawler",
                    })
                    added += 1

                if i + batch_size < len(new_ids):
                    await asyncio.sleep(2)

            await self.firestore_service.update_crawler_state("idle", added)
            print(f"[crawler] Done. Added {added} videos to pool.")
            return added

        except Exception as e:
            print(f"[crawler] Error: {e}")
            await self.firestore_service.update_crawler_state("error", 0)
            raise

    async def seed_videos(self, video_ids: list[str]) -> int:
        existing_ids = set(await self.firestore_service.get_all_active_video_ids())
        new_ids = [vid for vid in video_ids if vid not in existing_ids]
        if not new_ids:
            print(f"[seed] All {len(video_ids)} videos already in pool")
            return 0

        results = await self.feed_service.get_feed(new_ids)
        added = 0
        for item in results:
            video_id = item["youtube"]["video_id"]
            await self.firestore_service.upsert_feed_item(video_id, {
                "youtube": item["youtube"],
                "kalshi": item["kalshi"],
                "keywords": item.get("keywords", []),
                "crawled_at": datetime.now(timezone.utc),
                "source": "seed",
            })
            added += 1

        print(f"[seed] Added {added}/{len(video_ids)} videos to pool.")
        return added

    async def cleanup_stale(self, max_age_hours: int = 24) -> int:
        count = await self.firestore_service.deactivate_stale_items(max_age_hours)
        print(f"[cleanup] Deactivated {count} stale items (>{max_age_hours}h old)")
        return count
