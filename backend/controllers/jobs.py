# Job controller for video generation pipeline
import logging
from datetime import datetime

from blacksheep import json, Response
from blacksheep.server.controllers import APIController, post, get
from services.job_service import JobService
from models.job import VideoJobRequest
from utils.shorts_style import normalize_shorts_style

logger = logging.getLogger("jobs_controller")

def log_api(endpoint: str, msg: str):
    print(f"[{datetime.now().isoformat()}] [API] {endpoint}: {msg}", flush=True)

class Jobs(APIController):
    def __init__(self, job_service: JobService):
        self.job_service = job_service

    @staticmethod
    def _coerce_list(value) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            rows = value.replace("\r", "\n").split("\n")
            return [
                item.strip()
                for row in rows
                for item in row.split(",")
                if item.strip()
            ]
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _coerce_payload(self, payload: dict) -> dict:
        # Handle character image URLs (new key + legacy aliases).
        char_urls = self._coerce_list(
            payload.get("character_image_urls")
            or payload.get("characterImageUrls")
            or payload.get("reference_image_urls")
            or payload.get("referenceImageUrls")
        )

        return {
            "title": payload.get("title"),
            "outcome": payload.get("outcome") or payload.get("caption"),
            "original_bet_link": (
                payload.get("original_bet_link")
                or payload.get("originalBetLink")
                or payload.get("bet_link")
            ),
            "duration_seconds": payload.get("duration_seconds", 8),
            "shorts_style": (
                payload.get("shorts_style")
                or payload.get("shortsStyle")
                or payload.get("style")
            ),
            "source_image_url": payload.get("source_image_url") or payload.get("sourceImageUrl"),
            "character_image_urls": char_urls,
        }

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
        original_bet_link = (payload.get("original_bet_link") or "").strip()

        log_api("/create", f"Title: {title[:50]}...")
        log_api("/create", f"Outcome: {outcome[:50]}...")
        log_api("/create", f"Bet link: {original_bet_link}")

        if not title or not outcome or not original_bet_link:
            log_api("/create", "ERROR: Missing required fields")
            return json(
                {
                    "error": (
                        "title, outcome, and original_bet_link are required"
                    )
                },
                status=400,
            )

        try:
            duration_seconds = int(payload.get("duration_seconds", 6))
        except Exception:
            duration_seconds = 6

        shorts_style = normalize_shorts_style(payload.get("shorts_style"))
        source_image_url = (payload.get("source_image_url") or "").strip() or None
        character_image_urls = [u for u in payload.get("character_image_urls", []) if u]
        log_api("/create", f"Style: {shorts_style}, Character images: {len(character_image_urls)}")

        job_request = VideoJobRequest(
            title=title,
            outcome=outcome,
            original_bet_link=original_bet_link,
            duration_seconds=max(5, min(duration_seconds, 8)),
            shorts_style=shorts_style,
            source_image_url=source_image_url,
            character_image_urls=character_image_urls,
        )

        log_api("/create", f"Creating video job (duration={job_request.duration_seconds}s)...")
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
            "original_bet_link": status.original_bet_link,
            "image_url": status.image_url,
        }
        logger.debug(f"Job {job_id} status response: status={status.status}")
        if status.image_url:
            logger.info(f"Job {job_id} has image_url")
        if status.status == "done":
            logger.info(f"Job {job_id} DONE, video_url={status.video_url}")
        return json(response_data)
