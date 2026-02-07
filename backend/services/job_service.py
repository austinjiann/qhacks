import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
from google.cloud import storage

from models.job import JobStatus, VideoJobRequest
from services.vertex_service import VertexService
from utils.env import settings
from utils.gemini_prompt_builder import create_first_image_prompt
from utils.veo_prompt_builder import create_video_prompt

logger = logging.getLogger("job_service")


async def fetch_image_from_url(url: str) -> Optional[bytes]:
    """Fetch image bytes from URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    return await response.read()
    except Exception as e:
        print(f"Failed to fetch image from {url}: {e}", flush=True)
    return None


class JobService:
    def __init__(self, vertex_service: VertexService):
        logger.info("Initializing JobService...")
        self.vertex_service = vertex_service
        self.jobs: dict[str, dict] = {}

        self.local_queue: asyncio.Queue[dict] = asyncio.Queue()
        self.local_worker_task: asyncio.Task | None = None

        self.cloud_tasks = None
        if settings.WORKER_SERVICE_URL:
            from services.cloud_tasks_service import CloudTasksService

            self.cloud_tasks = CloudTasksService()
            logger.info(f"CloudTasks enabled, worker URL: {settings.WORKER_SERVICE_URL}")
        else:
            logger.info("CloudTasks disabled, using local worker queue")

        self.storage_client: storage.Client | None = None
        self.bucket = None
        if settings.GOOGLE_CLOUD_BUCKET_NAME:
            try:
                logger.info(f"Initializing GCS client for bucket: {settings.GOOGLE_CLOUD_BUCKET_NAME}")
                self.storage_client = storage.Client(
                    project=settings.GOOGLE_CLOUD_PROJECT or None
                )
                self.bucket = self.storage_client.bucket(settings.GOOGLE_CLOUD_BUCKET_NAME)
                logger.info(f"GCS bucket initialized successfully: {self.bucket.name}")
            except Exception as exc:
                logger.error(f"Failed to initialize GCS job persistence: {exc}")
        else:
            logger.warning("GOOGLE_CLOUD_BUCKET_NAME not set - job persistence disabled")

    def _job_blob_path(self, job_id: str) -> str:
        return f"jobs/{job_id}.json"

    def _image_blob_path(self, job_id: str, image_num: int) -> str:
        return f"images/{job_id}/image{image_num}.png"

    def _upload_image_sync(self, job_id: str, image_num: int, image_data: bytes) -> str:
        """Upload an image to GCS and return the gs:// URI."""
        if not self.bucket:
            logger.warning(f"_upload_image_sync: No bucket configured, cannot save image")
            return ""

        blob_path = self._image_blob_path(job_id, image_num)
        logger.info(f"[{job_id}] Uploading image {image_num} to {blob_path} ({len(image_data)} bytes)")

        blob = self.bucket.blob(blob_path)
        blob.upload_from_string(image_data, content_type="image/png")

        gs_uri = f"gs://{self.bucket.name}/{blob_path}"
        logger.info(f"[{job_id}] Image {image_num} uploaded: {gs_uri}")
        return gs_uri

    def _generate_signed_url(self, gs_uri: str, expiration_hours: int = 24) -> Optional[str]:
        """Generate a URL for a GCS object. Uses public URL (bucket must be public)."""
        if not gs_uri or not gs_uri.startswith("gs://"):
            return None

        # Just use public URL - signed URLs require service account key file
        # To use this, run: gsutil iam ch allUsers:objectViewer gs://YOUR_BUCKET_NAME
        public_url = f"https://storage.googleapis.com/{gs_uri[5:]}"
        logger.info(f"_generate_signed_url: Using public URL: {public_url}")
        return public_url

    def _parse_timestamp(self, value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None

    def _to_public_url(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if value.startswith("gs://"):
            public_url = f"https://storage.googleapis.com/{value[len('gs://'):]}"
            logger.debug(f"_to_public_url: {value} -> {public_url}")
            return public_url
        return value

    def _download_job_sync(self, job_id: str) -> Optional[dict]:
        if not self.bucket or not self.storage_client:
            logger.debug(f"_download_job_sync: no bucket/client for job {job_id}")
            return None

        blob_path = self._job_blob_path(job_id)
        logger.debug(f"_download_job_sync: checking blob {blob_path}")
        blob = self.bucket.blob(blob_path)
        if not blob.exists(client=self.storage_client):
            logger.debug(f"_download_job_sync: blob does not exist: {blob_path}")
            return None

        logger.debug(f"_download_job_sync: downloading blob {blob_path}")
        raw = blob.download_as_text()
        data = json.loads(raw)
        logger.info(f"_download_job_sync: loaded job {job_id} from GCS, status={data.get('status')}")
        return data if isinstance(data, dict) else None

    def _upload_job_sync(self, job_id: str, data: dict):
        if not self.bucket:
            logger.debug(f"_upload_job_sync: no bucket configured for job {job_id}")
            return
        blob_path = self._job_blob_path(job_id)
        logger.info(f"_upload_job_sync: uploading job {job_id} to {blob_path}, status={data.get('status')}")
        blob = self.bucket.blob(blob_path)
        blob.upload_from_string(
            json.dumps(data, separators=(",", ":"), sort_keys=True),
            content_type="application/json",
        )
        logger.debug(f"_upload_job_sync: upload complete for job {job_id}")

    async def _save_job(self, job_id: str, data: dict):
        self.jobs[job_id] = data
        if self.bucket:
            try:
                await asyncio.to_thread(self._upload_job_sync, job_id, data)
            except Exception as exc:
                print(f"Failed to persist job {job_id} to bucket: {exc}")

    async def _load_job(self, job_id: str, prefer_remote: bool = False) -> Optional[dict]:
        job = self.jobs.get(job_id)
        if job and not prefer_remote:
            return job

        if self.bucket:
            try:
                remote_job = await asyncio.to_thread(self._download_job_sync, job_id)
            except Exception as exc:
                print(f"Failed to read job {job_id} from bucket: {exc}")
                return job

            if remote_job:
                self.jobs[job_id] = remote_job
                return remote_job

        return job

    async def _ensure_local_worker(self):
        if self.cloud_tasks:
            return

        if self.local_worker_task and not self.local_worker_task.done():
            return

        self.local_worker_task = asyncio.create_task(self._local_worker_loop())

    async def _local_worker_loop(self):
        while True:
            item = await self.local_queue.get()
            job_id = item.get("job_id", "unknown")
            try:
                await self.process_video_job(job_id, item)
            except Exception as exc:
                print(f"[{job_id[:8]}] FAILED: {exc}", flush=True)
                traceback.print_exc()
            finally:
                self.local_queue.task_done()

    async def create_video_job(self, request: VideoJobRequest) -> str:
        """Create a video job."""
        job_id = str(uuid.uuid4())

        await self._save_job(
            job_id,
            {
                "status": "pending",
                "job_start_time": datetime.now().isoformat(),
                "title": request.title,
                "caption": request.caption,
                "original_bet_link": request.original_bet_link,
                "duration_seconds": request.duration_seconds,
                "source_image_url": request.source_image_url,
            },
        )

        job_data = {
            "title": request.title,
            "caption": request.caption,
            "original_bet_link": request.original_bet_link,
            "duration_seconds": request.duration_seconds,
            "source_image_url": request.source_image_url,
        }

        if self.cloud_tasks:
            self.cloud_tasks.enqueue_video_job(job_id, job_data)
        else:
            await self._ensure_local_worker()
            await self.local_queue.put({"job_id": job_id, **job_data})

        return job_id

    async def process_video_job(self, job_id: str, job_data: dict):
        """Process pipeline: source_image -> first_frame -> video"""
        jid = job_id[:8]
        start_time = datetime.now().isoformat()
        existing_job = await self._load_job(job_id)

        try:
            title = job_data["title"]
            caption = job_data["caption"]
            original_bet_link = job_data["original_bet_link"]
            duration = int(job_data.get("duration_seconds", 8))
            source_image_url = job_data.get("source_image_url")

            # Fetch source image if URL provided
            source_image = None
            if source_image_url:
                source_image = await fetch_image_from_url(source_image_url)
                if source_image:
                    print(f"[{jid}] Using source image ({len(source_image)} bytes)", flush=True)

            # Generate first frame (from source image if available)
            first_prompt = create_first_image_prompt(title=title, caption=caption, original_bet_link=original_bet_link)
            first_image = await self.vertex_service.generate_image_from_prompt(
                prompt=first_prompt,
                image=source_image
            )

            image_uri = ""
            if self.bucket:
                image_uri = await asyncio.to_thread(self._upload_image_sync, job_id, 1, first_image)

            # Generate video from first frame (Veo decides what happens next)
            veo_prompt = create_video_prompt(title=title, caption=caption, original_bet_link=original_bet_link)
            operation = await self.vertex_service.generate_video_content(
                prompt=veo_prompt,
                image_data=first_image,
                duration_seconds=duration,
            )

            await self._save_job(job_id, {
                "status": "processing",
                "operation_name": operation.name,
                "job_start_time": existing_job.get("job_start_time") if existing_job else start_time,
                "title": title,
                "caption": caption,
                "original_bet_link": original_bet_link,
                "duration_seconds": duration,
                "image_uri": image_uri,
            })
            print(f"[{jid}] Video processing started", flush=True)

        except Exception as exc:
            print(f"[{jid}] ERROR: {exc}", flush=True)
            await self._save_job(job_id, {
                "status": "error",
                "error": str(exc),
                "job_start_time": existing_job.get("job_start_time") if existing_job else start_time,
                "title": job_data.get("title"),
                "caption": job_data.get("caption"),
                "original_bet_link": job_data.get("original_bet_link"),
                "duration_seconds": int(job_data.get("duration_seconds", 8)),
            })

    def _get_image_signed_url(self, job: dict) -> Optional[str]:
        """Generate signed URL for the start frame image."""
        image_uri = job.get("image_uri")
        if image_uri:
            return self._generate_signed_url(image_uri)
        return None

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Poll job status."""
        job = await self._load_job(job_id, prefer_remote=bool(self.bucket))
        if job is None:
            return None

        status = job.get("status")
        job_start_time = self._parse_timestamp(job.get("job_start_time"))
        job_end_time = self._parse_timestamp(job.get("job_end_time"))
        original_bet_link = job.get("original_bet_link")
        image_url = self._get_image_signed_url(job)

        if status in ("pending", "queued"):
            return JobStatus(status="waiting", job_start_time=job_start_time, original_bet_link=original_bet_link, image_url=image_url)

        if status == "error":
            return JobStatus(status="error", job_start_time=job_start_time, job_end_time=job_end_time, error=job.get("error"), original_bet_link=original_bet_link, image_url=image_url)

        if status == "done":
            video_url = job.get("video_url")
            video_uri = job.get("video_uri")
            if video_uri:
                video_url = self._generate_signed_url(video_uri)
            return JobStatus(status="done", job_start_time=job_start_time, job_end_time=job_end_time, video_url=video_url, original_bet_link=original_bet_link, image_url=image_url)

        if status == "processing" and job.get("operation_name"):
            result = await self.vertex_service.get_video_status_by_name(job["operation_name"])
            if result.status == "done":
                video_uri = result.video_url
                video_url = self._generate_signed_url(video_uri) if video_uri else None
                job["status"] = "done"
                job["video_uri"] = video_uri
                job["video_url"] = video_url
                job["job_end_time"] = datetime.now().isoformat()
                await self._save_job(job_id, job)
                print(f"[{job_id[:8]}] Video complete", flush=True)
                return JobStatus(status="done", job_start_time=job_start_time, job_end_time=self._parse_timestamp(job["job_end_time"]), video_url=video_url, original_bet_link=original_bet_link, image_url=image_url)
            if result.status == "error":
                job["status"] = "error"
                job["error"] = result.error
                await self._save_job(job_id, job)
                return JobStatus(status="error", error=result.error, original_bet_link=original_bet_link, image_url=image_url)
            return JobStatus(status="waiting", job_start_time=job_start_time, original_bet_link=original_bet_link, image_url=image_url)

        return JobStatus(status="waiting", job_start_time=job_start_time, original_bet_link=original_bet_link, image_url=image_url)

    async def update_job(self, job_id: str, data: dict):
        existing = await self._load_job(job_id) or {}
        existing.update(data)
        await self._save_job(job_id, existing)
