from blacksheep import Request, json
from blacksheep.server.controllers import APIController, get, post

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

    @get("/candlesticks")
    async def get_candlesticks(
        self,
        ticker: str = "",
        series_ticker: str = "",
        period: int = 1,
        hours: int = 2,
        start_ts: int = 0,
        end_ts: int = 0,
    ):
        if not ticker or not series_ticker:
            return json({"error": "ticker and series_ticker required"}, status=400)
        if period not in (1, 60, 1440):
            return json({"error": "period must be 1, 60, or 1440"}, status=400)
        sanitized_start_ts = start_ts if isinstance(start_ts, int) and start_ts > 0 else None
        sanitized_end_ts = end_ts if isinstance(end_ts, int) and end_ts > 0 else None

        if sanitized_start_ts and sanitized_end_ts and sanitized_start_ts >= sanitized_end_ts:
            return json({"error": "start_ts must be less than end_ts"}, status=400)
        try:
            candlesticks = await self.feed_service.get_candlesticks(
                series_ticker,
                ticker,
                period_interval=period,
                hours=hours,
                start_ts=sanitized_start_ts,
                end_ts=sanitized_end_ts,
            )
            return json({"candlesticks": candlesticks})
        except Exception as e:
            return json({"error": str(e)}, status=500)
        
    @post("/advice")
    async def get_advice(self, request: Request):
        try:
            data = await request.json()
        except Exception:
            return json({"error": "Invalid JSON body"}, status=400)
        question = data.get("question", "")
        side = data.get("side", "YES")
        amount = data.get("amount", 0)
        yes_price = data.get("yes_price", 50)
        no_price = data.get("no_price", 50)
        if not question:
            return json({"error": "question is required"}, status=400)
        advice = await self.feed_service.get_trade_advice(
            question, side, amount, yes_price, no_price
        )
        return json({"advice": advice})
    
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
