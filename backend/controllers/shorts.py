from blacksheep import json
from blacksheep.server.controllers import APIController, get

from services.feed_service import FeedService


class Shorts(APIController):
    def __init__(self, feed_service: FeedService):
        self.feed_service = feed_service

    @classmethod
    def route(cls):
        return "/shorts"

    @get("/health")
    async def health_check(self):
        return json({"status": "ok"})

    @get("/match")
    async def match_video(self, video_id: str = ""):
        if not video_id:
            return json({"error": "video_id required"}, status=400)
        result = await self.feed_service.match_video(video_id)
        if not result:
            return json({"error": "No matching market found"}, status=404)
        return json(result)

    @get("/feed")
    async def get_feed(self, video_ids: str = "", limit: int = 10):
        if not video_ids:
            return json({"error": "video_ids required"}, status=400)
        ids = [v.strip() for v in video_ids.split(",") if v.strip()][:limit]
        if not ids:
            return json({"error": "No valid video_ids provided"}, status=400)
        results = await self.feed_service.get_feed(ids)
        feed = []
        for i, item in enumerate(results):
            feed.append({
                "id": str(i + 1),
                "youtube": item["youtube"],
                "kalshi": item["kalshi"],
            })
        return json(feed)
