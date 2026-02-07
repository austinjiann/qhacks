# Job controller for video generation pipeline
import json as json_lib
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
            "caption": payload.get("caption"),
            "original_bet_link": (
                payload.get("original_bet_link")
                or payload.get("originalBetLink")
                or payload.get("originla_bet_link")
                or payload.get("bet_link")
                or payload.get("bet")
            ),
            "duration_seconds": payload.get("duration_seconds", 8),
            "source_image_url": payload.get("source_image_url") or payload.get("sourceImageUrl"),
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
        caption = (payload.get("caption") or "").strip()
        original_bet_link = (payload.get("original_bet_link") or "").strip()

        log_api("/create", f"Title: {title[:50]}...")
        log_api("/create", f"Caption: {caption[:50]}...")
        log_api("/create", f"Bet link: {original_bet_link}")

        if not title or not caption or not original_bet_link:
            log_api("/create", "ERROR: Missing required fields")
            return json(
                {
                    "error": (
                        "title, caption, and original_bet_link are required"
                    )
                },
                status=400,
            )

        try:
            duration_seconds = int(payload.get("duration_seconds", 6))
        except Exception:
            duration_seconds = 6

        source_image_url = (payload.get("source_image_url") or "").strip() or None

        job_request = VideoJobRequest(
            title=title,
            caption=caption,
            original_bet_link=original_bet_link,
            duration_seconds=max(5, min(duration_seconds, 8)),  # Veo supports 5-8 seconds
            source_image_url=source_image_url,
        )

        log_api("/create", f"Creating video job (duration={job_request.duration_seconds}s)...")
        job_id = await self.job_service.create_video_job(job_request)
        log_api("/create", f"Job created: {job_id}")
        log_api("/create", "Job queued to worker - pipeline starting in background")
        return json({"job_id": job_id})

    @get("/debug")
    async def debug_info(self) -> Response:
        """Debug endpoint to check worker status."""
        worker_task = self.job_service.local_worker_task
        worker_status = "not_started"
        if worker_task:
            if worker_task.done():
                try:
                    worker_task.result()
                    worker_status = "completed"
                except Exception as e:
                    worker_status = f"crashed: {e}"
            else:
                worker_status = "running"

        info = {
            "cloud_tasks_enabled": self.job_service.cloud_tasks is not None,
            "local_worker_status": worker_status,
            "queue_size": self.job_service.local_queue.qsize(),
            "jobs_in_memory": len(self.job_service.jobs),
            "bucket_configured": self.job_service.bucket is not None,
        }
        log_api("/debug", f"Debug info: {info}")
        return json(info)

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
