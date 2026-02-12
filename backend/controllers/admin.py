from blacksheep import json
from blacksheep.server.controllers import APIController, get, post

from services.crawler_service import CrawlerService
from services.firestore_service import FirestoreService


class Admin(APIController):
    def __init__(self, crawler_service: CrawlerService, firestore_service: FirestoreService):
        self.crawler_service = crawler_service
        self.firestore_service = firestore_service

    @classmethod
    def route(cls):
        return "/admin"

    @post("/crawl")
    async def crawl(self, query: str = "", max_videos: int = 5):
        added = await self.crawler_service.crawl_and_match(
            query=query or None,
            max_videos=max_videos,
        )
        return json({"status": "done", "videos_added": added})

    @post("/cleanup")
    async def cleanup(self, max_age_hours: int = 24):
        count = await self.crawler_service.cleanup_stale(max_age_hours)
        return json({"status": "done", "deactivated": count})

    @post("/purge")
    async def purge(self):
        count = await self.firestore_service.purge_all_items()
        return json({"status": "done", "deleted": count})

    @post("/purge-sports")
    async def purge_sports(self):
        sports_keywords = [
            "nfl", "nba", "mlb", "nhl",
            "super bowl", "superbowl",
            "football", "basketball", "baseball", "hockey",
            "premier league", "champions league", "soccer",
            "lakers", "celtics", "warriors", "chiefs", "eagles",
            "patriots", "seahawks",
        ]
        count = await self.firestore_service.deactivate_by_keywords(sports_keywords)
        return json({"status": "done", "deactivated": count})

    @post("/reactivate")
    async def reactivate(self):
        count = await self.firestore_service.reactivate_all_items()
        return json({"status": "done", "reactivated": count})

    @post("/seed")
    async def seed(self, video_ids: str = ""):
        ids = [v.strip() for v in video_ids.split(",") if v.strip()]
        if not ids:
            return json({"error": "video_ids required"}, status=400)
        added = await self.crawler_service.seed_videos(ids)
        return json({"status": "done", "videos_added": added, "total_requested": len(ids)})

    @get("/pool/items")
    async def pool_items(self, limit: int = 50):
        items = await self.firestore_service.list_pool_items(limit)
        result = []
        for item in items:
            result.append({
                "video_id": item.get("video_id", ""),
                "title": item.get("youtube", {}).get("title", ""),
                "source": item.get("source", ""),
                "keywords": item.get("keywords", []),
                "markets": len(item.get("kalshi", [])),
            })
        return json(result)

    @get("/pool/stats")
    async def pool_stats(self):
        stats = await self.firestore_service.get_pool_stats()
        return json(stats)
