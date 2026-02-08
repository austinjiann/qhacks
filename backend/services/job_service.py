import asyncio
import json
import logging
import os
import shutil
import tempfile
import traceback
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from google.cloud import storage
import aiohttp
from models.job import JobStatus, VideoJobRequest
from services.vertex_service import VertexService
from utils.env import settings
from utils.gemini_prompt_builder import create_first_image_prompt
from utils.veo_prompt_builder import create_video_prompt

logger = logging.getLogger("job_service")
IMAGE_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/png,image/jpeg,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _looks_like_image(data: bytes) -> bool:
    if not data:
        return False
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if data.startswith(b"\xff\xd8\xff"):
        return True
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return True
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return True
    if len(data) > 12 and data[4:12] == b"ftypavif":
        return True
    return False


async def fetch_image_from_url(url: str) -> Optional[bytes]:
    """Fetch image bytes from URL."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    request_headers = {
        **IMAGE_REQUEST_HEADERS,
        "Referer": f"{parsed.scheme}://{parsed.netloc}/",
    }
    try:
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(headers=request_headers, connector=connector) as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as response:
                if response.status != 200:
                    return None
                payload = await response.read()
                content_type = (response.headers.get("Content-Type") or "").lower()
                if content_type.startswith("image/") or _looks_like_image(payload):
                    return payload
    except Exception as e:
        print(f"Failed to fetch image from {url}: {e}", flush=True)
    return None


class JobService:
    def __init__(self, vertex_service: VertexService):
        logger.info("Initializing JobService...")
        self.vertex_service = vertex_service

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
        
        self._bucket_cache: dict[str, storage.Bucket] = {}

    def _split_gs_uri(self, gs_uri: str) -> tuple[str, str] | None:
        if not gs_uri or not gs_uri.startswith("gs://"):
            return None
        path = gs_uri[5:]
        if "/" not in path:
            return None
        bucket_name, blob_name = path.split("/", 1)
        if not bucket_name or not blob_name:
            return None
        return bucket_name, blob_name

    def _get_bucket(self, bucket_name: str) -> Optional[storage.Bucket]:
        if not bucket_name or not self.storage_client:
            return None
        if self.bucket and self.bucket.name == bucket_name:
            return self.bucket
        if bucket_name in self._bucket_cache:
            return self._bucket_cache[bucket_name]
        bucket = self.storage_client.bucket(bucket_name)
        self._bucket_cache[bucket_name] = bucket
        return bucket

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

    def _generate_signed_url(self, gs_uri: str) -> Optional[str]:
        if not gs_uri or not gs_uri.startswith("gs://"):
            return None

        public_url = f"https://storage.googleapis.com/{gs_uri[5:]}"
        logger.info(f"_generate_signed_url: Using public URL: {public_url}")
        return public_url

    def _download_job_sync(self, job_id: str) -> Optional[dict]:
        if not self.bucket or not self.storage_client:
            logger.debug(f"_download_job_sync: no bucket/client for job {job_id}")
            return None

        blob_path = f"jobs/{job_id}.json"
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
        blob_path = f"jobs/{job_id}.json"
        logger.info(f"_upload_job_sync: uploading job {job_id} to {blob_path}, status={data.get('status')}")
        blob = self.bucket.blob(blob_path)
        blob.upload_from_string(
            json.dumps(data, separators=(",", ":"), sort_keys=True),
            content_type="application/json",
        )
        logger.debug(f"_upload_job_sync: upload complete for job {job_id}")

    async def _save_job(self, job_id: str, data: dict):
        if self.bucket:
            try:
                await asyncio.to_thread(self._upload_job_sync, job_id, data)
            except Exception as exc:
                print(f"Failed to persist job {job_id} to bucket: {exc}")

    async def _load_job(self, job_id: str) -> Optional[dict]:
        if not self.bucket or not self.storage_client:
            return None

        try:
            return await asyncio.to_thread(self._download_job_sync, job_id)
        except Exception as exc:
            logger.error(f"Failed to load job {job_id} from GCS: {exc}")
            return None

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
        job_id = str(uuid.uuid4())

        await self._save_job(
            job_id,
            {
                "status": "pending",
                "job_start_time": datetime.now().isoformat(),
                "title": request.title,
                "outcome": request.outcome,
                "original_bet_link": request.original_bet_link,
                "source_image_url": request.source_image_url,
            },
        )

        job_data = {
            "title": request.title,
            "outcome": request.outcome,
            "original_bet_link": request.original_bet_link,
            "source_image_url": request.source_image_url,
        }

        if self.cloud_tasks:
            self.cloud_tasks.enqueue_video_job(job_id, job_data)
        else:
            await self._ensure_local_worker()
            await self.local_queue.put({"job_id": job_id, **job_data})

        return job_id

    async def process_video_job(self, job_id: str, job_data: dict):
        #  Gemini starting frame -> Veo video
        jid = job_id[:8]
        start_time = datetime.now().isoformat()
        existing_job = await self._load_job(job_id)

        try:
            title = job_data["title"]
            outcome = (job_data.get("outcome") or job_data.get("caption") or "").strip()
            if not outcome:
                raise ValueError("outcome is required")
            original_bet_link = job_data["original_bet_link"]
            source_image_url = job_data.get("source_image_url")

            # starting frame
            source_image = None
            if source_image_url:
                source_image = await fetch_image_from_url(source_image_url)
                if source_image:
                    print(f"[{jid}] Using provided source image ({len(source_image)} bytes)", flush=True)
                else:
                    print(f"[{jid}] source_image_url could not be fetched; will generate via Gemini", flush=True)

            if not source_image:
                print(f"[{jid}] Generating starting frame via Gemini...", flush=True)
                image_prompt = create_first_image_prompt(
                    title=title,
                    outcome=outcome,
                    original_bet_link=original_bet_link,
                )
                source_image = await self.vertex_service.generate_starting_frame(image_prompt)
                if source_image:
                    print(f"[{jid}] Gemini starting frame generated ({len(source_image)} bytes)", flush=True)
                else:
                    raise ValueError("Failed to generate starting frame via Gemini and no source image provided")

            # starting frame -> GCS
            image_uri = ""
            if self.bucket and source_image:
                image_uri = await asyncio.to_thread(self._upload_image_sync, job_id, 1, source_image)

            # generate video with prompt and inputs
            veo_prompt = create_video_prompt(
                title=title,
                outcome=outcome,
                original_bet_link=original_bet_link,
            )
            operation = await self.vertex_service.generate_video_content(
                prompt=veo_prompt,
                image_data=source_image,
            )

            await self._save_job(job_id, {
                "status": "processing",
                "operation_name": operation.name,
                "job_start_time": existing_job.get("job_start_time") if existing_job else start_time,
                "title": title,
                "outcome": outcome,
                "original_bet_link": original_bet_link,
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
                "outcome": job_data.get("outcome") or job_data.get("caption"),
                "original_bet_link": job_data.get("original_bet_link"),
            })

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        job = await self._load_job(job_id)
        if job is None:
            return None

        status = job.get("status")
        job_start_time = (
            datetime.fromisoformat(job["job_start_time"])
            if job.get("job_start_time")
            else None
        )
        job_end_time = (
            datetime.fromisoformat(job["job_end_time"])
            if job.get("job_end_time")
            else None
        )
        original_bet_link = job.get("original_bet_link")
        image_url = job.get("image_uri")

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
                return JobStatus(status="done", job_start_time=job_start_time, job_end_time=job_end_time, video_url=video_url, original_bet_link=original_bet_link, image_url=image_url)
            if result.status == "error":
                job["status"] = "error"
                job["error"] = result.error
                await self._save_job(job_id, job)
                return JobStatus(status="error", error=result.error, original_bet_link=original_bet_link, image_url=image_url)
            return JobStatus(status="waiting", job_start_time=job_start_time, original_bet_link=original_bet_link, image_url=image_url)

        return JobStatus(status="waiting", job_start_time=job_start_time, original_bet_link=original_bet_link, image_url=image_url)
