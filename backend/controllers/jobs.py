# Job controller for video generation pipeline
import logging
from datetime import datetime

from blacksheep import json, Response
from blacksheep.server.controllers import APIController, post, get
from services.job_service import JobService
from models.job import VideoJobRequest

logger = logging.getLogger("jobs_controller")

def log_api(endpoint: str, msg: str):
    print(f"[{datetime.now().isoformat()}] [API] {endpoint}: {msg}", flush=True)

class Jobs(APIController):
    def __init__(self, job_service: JobService):
        self.job_service = job_service

    def _coerce_payload(self, payload: dict) -> dict:
        return {
            "title": payload.get("title"),
            # New schema uses "outcome"; keep "caption" as backward-compatible fallback.
            "outcome": payload.get("outcome") or payload.get("caption"),
            "original_trade_link": (
                payload.get("original_trade_link")
                or payload.get("originalTradeLink")
                or payload.get("originla_trade_link")
                or payload.get("trade_link")
                or payload.get("trade")
            ),
            "source_image_url": payload.get("source_image_url") or payload.get("sourceImageUrl"),
            "kalshi": payload.get("kalshi"),
            "trade_side": payload.get("trade_side"),
        }
        
    @get("/health")
    async def health_check(self):
        return json({"status": "ok"})

    @post("/create")
    async def create_job(self, request):
        log_api("/create", "========== REQUEST RECEIVED ==========")
        body = None
        try:
            body = await request.json()
            log_api("/create", f"Parsed JSON body")
        except Exception as e:
            log_api("/create", f"JSON parse failed, trying form: {e}")
            form = await request.form()
            normalized = {}
            for k, v in form.items():
                if isinstance(k, bytes):
                    key = k.decode()
                else:
                    key = str(k)

                val = v
                if isinstance(val, (list, tuple)):
                    val = val[0] if val else ""
                if isinstance(val, bytes):
                    try:
                        val = val.decode()
                    except Exception:
                        val = str(val)
                normalized[key] = val
            body = normalized

        payload = self._coerce_payload(body)
        title = (payload.get("title") or "").strip()
        outcome = (payload.get("outcome") or "").strip()
        original_trade_link = (payload.get("original_trade_link") or "").strip()
        source_image_url = (payload.get("source_image_url") or "").strip()

        log_api("/create", f"Title: {title[:50]}...")
        log_api("/create", f"Outcome: {outcome[:50]}...")
        log_api("/create", f"Trade link: {original_trade_link}")

        if not title or not outcome or not original_trade_link:
            log_api("/create", "ERROR: Missing required fields")
            return json(
                {"error": "title, outcome, and original_trade_link are required"},

                status=400,
            )

        kalshi = payload.get("kalshi")
        trade_side = payload.get("trade_side")

        job_request = VideoJobRequest(
            title=title,
            outcome=outcome,
            original_trade_link=original_trade_link,
            source_image_url=source_image_url or None,
            kalshi=kalshi,
            trade_side=trade_side,
        )

        log_api("/create", "Creating video job...")
        job_id = await self.job_service.create_video_job(job_request)
        log_api("/create", f"Job created: {job_id}")
        log_api("/create", "Job queued to worker - pipeline starting in background")
        return json({"job_id": job_id})

    @get("/status/{job_id}")
    async def get_status(self, job_id: str) -> Response:
        logger.debug(f"GET /api/jobs/status/{job_id}")
        status = await self.job_service.get_job_status(job_id)

        if status is None:
            logger.warning(f"Job {job_id} not found")
            return json({"error": "Job not found"}, status=404)

        response_data = {
            "status": status.status,
            "video_url": status.video_url,
            "error": status.error,
            "original_trade_link": status.original_trade_link,
            "image_url": status.image_url,
        }
        logger.debug(f"Job {job_id} status response: status={status.status}")
        if status.image_url:
            logger.info(f"Job {job_id} has image_url")
        if status.status == "done":
            logger.info(f"Job {job_id} DONE, video_url={status.video_url}")
        return json(response_data)
