from blacksheep import json
from blacksheep.server.controllers import APIController, get, post

from services.firestore_service import FirestoreService


class Pool(APIController):
    def __init__(self, firestore_service: FirestoreService):
        self.firestore_service = firestore_service

    @classmethod
    def route(cls):
        return "/pool"

    @get("/feed")
    async def get_feed(self, count: int = 10, exclude: str = ""):
        exclude_ids = set(v.strip() for v in exclude.split(",") if v.strip()) if exclude else None
        items = await self.firestore_service.get_random_feed_items(count, exclude_ids=exclude_ids)
        feed = []
        for item in items:
            video_id = item.get("_doc_id", "")
            feed.append({
                "id": video_id,
                "youtube": item.get("youtube", {}),
                "kalshi": item.get("kalshi", []),
                "keywords": item.get("keywords", []),
                "source": item.get("source", ""),
            })
        return json(feed)

    @post("/generated/{job_id}/consume")
    async def consume_generated(self, job_id: str):
        await self.firestore_service.mark_consumed(job_id)
        return json({"status": "consumed"})

    @post("/feed/{video_id}/delete")
    async def delete_feed_item(self, video_id: str):
        removed = await self.firestore_service.deactivate_feed_item(video_id)
        return json({"status": "deleted" if removed else "not_found"})

    @get("/stats")
    async def get_stats(self):
        stats = await self.firestore_service.get_pool_stats()
        return json(stats)
