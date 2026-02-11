# google cloud run --> will be used when hosted
from blacksheep import json, Request, Response
from blacksheep.server.controllers import APIController, post, get
from services.job_service import JobService
from services.crawler_service import CrawlerService

class Worker(APIController):
    def __init__(self, job_service: JobService, crawler_service: CrawlerService):
        self.job_service = job_service
        self.crawler_service = crawler_service
        
    @get("/health")
    async def health_check(self):
        return json({"status": "ok"})
    
    @post("/greet")
    async def greet_user(self, name: str):
        return {"message": f"Hello, {name}!"}

    @post("/process")
    async def process_job(self, data: dict) -> Response:
        # Support queued legacy jobs that still send "caption".
        if not data.get("outcome") and data.get("caption"):
            data["outcome"] = data.get("caption")

        required = ("job_id", "title", "outcome", "original_trade_link")
        missing = [key for key in required if not data.get(key)]
        if missing:
            return json(
                {"error": f"Missing required fields: {', '.join(missing)}"},
                status=400,
            )

        job_id = data["job_id"]

        # Process the job
        await self.job_service.process_video_job(job_id, data)

        return json({"status": "processing", "job_id": job_id})

    @post("/crawl")
    async def crawl(self, request: Request) -> Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        query = data.get("query")
        max_videos = data.get("max_videos", 10)
        added = await self.crawler_service.crawl_and_match(query=query, max_videos=max_videos)
        return json({"status": "done", "videos_added": added})

    @post("/cleanup")
    async def cleanup(self, request: Request) -> Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        max_age_hours = data.get("max_age_hours", 24)
        count = await self.crawler_service.cleanup_stale(max_age_hours)
        return json({"status": "done", "deactivated": count})
