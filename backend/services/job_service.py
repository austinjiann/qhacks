import asyncio
import json
import logging
import re
import traceback
import uuid
from datetime import datetime
from typing import Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import aiohttp
from google.cloud import storage

from models.job import JobStatus, VideoJobRequest
from services.vertex_service import VertexService
from utils.env import settings
from utils.gemini_prompt_builder import create_first_image_prompt
from utils.shorts_style import normalize_shorts_style
from utils.veo_prompt_builder import create_video_prompt

logger = logging.getLogger("job_service")

IMAGE_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/png,image/jpeg,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "image",
    "Sec-Fetch-Mode": "no-cors",
    "Sec-Fetch-Site": "cross-site",
}

MAX_CHARACTER_IMAGES = 2


def _unwrap_image_url(url: str) -> str:
    """Extract a direct image URL from common wrappers (e.g., Google image result links)."""
    cleaned = (url or "").strip()
    if not cleaned:
        return ""

    parsed = urlparse(cleaned)
    if parsed.netloc in {"www.google.com", "google.com"} and parsed.path.startswith("/imgres"):
        imgurl = parse_qs(parsed.query).get("imgurl", [None])[0]
        if imgurl:
            return unquote(imgurl)
    return cleaned


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


def _extract_image_candidates_from_html(html_text: str, base_url: str) -> list[str]:
    """Extract likely image asset URLs from an HTML page."""
    patterns = [
        r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]*content=["\']([^"\']+)["\']',
        r'<meta[^>]+itemprop=["\']image["\'][^>]*content=["\']([^"\']+)["\']',
        r'<link[^>]+rel=["\']image_src["\'][^>]*href=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+data-src=["\']([^"\']+)["\']',
    ]

    candidates: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, html_text, flags=re.IGNORECASE):
            candidate = _unwrap_image_url(urljoin(base_url, match.strip()))
            if candidate and candidate not in candidates:
                candidates.append(candidate)
            if len(candidates) >= 12:
                return candidates
    return candidates


async def _fetch_image_bytes(
    session: aiohttp.ClientSession,
    url: str,
    *,
    depth: int = 0,
    visited: set[str] | None = None,
) -> Optional[bytes]:
    target_url = _unwrap_image_url(url)
    if not target_url:
        return None

    if visited is None:
        visited = set()
    if target_url in visited:
        return None
    visited.add(target_url)

    parsed = urlparse(target_url)
    request_headers = {
        **IMAGE_REQUEST_HEADERS,
        "Referer": f"{parsed.scheme}://{parsed.netloc}/" if parsed.scheme and parsed.netloc else "",
    }

    try:
        print(f"[FETCH] Attempting to fetch: {target_url}", flush=True)
        async with session.get(
            target_url,
            timeout=aiohttp.ClientTimeout(total=15),
            allow_redirects=True,
            headers=request_headers,
        ) as response:
            print(f"[FETCH] Response status: {response.status}, headers: {dict(response.headers)}", flush=True)
            if response.status != 200:
                print(f"[FETCH] Failed to fetch image from {target_url}: HTTP {response.status}", flush=True)
                return None

            payload = await response.read()
            print(f"[FETCH] Received {len(payload)} bytes", flush=True)
            content_type = (response.headers.get("Content-Type") or "").lower()
            if content_type.startswith("image/") or _looks_like_image(payload):
                print(f"[FETCH] SUCCESS - valid image detected ({content_type})", flush=True)
                return payload

            print(f"[FETCH] Content-Type: {content_type}, looks_like_image: {_looks_like_image(payload)}", flush=True)
            print(f"[FETCH] First 50 bytes: {payload[:50]}", flush=True)

            # Fallback: page URL provided instead of direct image URL.
            if depth < 1 and ("text/html" in content_type or payload[:16].lstrip().startswith(b"<")):
                html_text = payload.decode("utf-8", errors="ignore")
                candidates = _extract_image_candidates_from_html(html_text, target_url)
                if candidates:
                    print(
                        f"Resolved {len(candidates)} image candidate(s) from page URL: {target_url}",
                        flush=True,
                    )
                for candidate_url in candidates:
                    img = await _fetch_image_bytes(
                        session,
                        candidate_url,
                        depth=depth + 1,
                        visited=visited,
                    )
                    if img:
                        return img

            preview = payload[:120].decode(errors="ignore").replace("\n", " ")
            print(
                (
                    "Fetched non-image content "
                    f"from {target_url}: Content-Type={content_type or 'unknown'}, "
                    f"preview={preview}"
                ),
                flush=True,
            )
            return None
    except Exception as exc:
        print(f"Failed to fetch image from {target_url}: {exc}", flush=True)
        return None


async def fetch_image_from_url(url: str) -> Optional[bytes]:
    """Fetch image bytes from URL."""
    # Disable SSL verification for fetching public images (many CDNs have cert issues)
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(headers=IMAGE_REQUEST_HEADERS, connector=connector) as session:
        return await _fetch_image_bytes(session, url)


def _is_probable_url(value: str) -> bool:
    parsed = urlparse((value or "").strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


async def _load_character_images(
    character_image_urls: list[str],
) -> list[bytes]:
    """
    Fetch character images from direct URLs with parallel best-effort retrieval.
    """
    unique_urls: list[str] = []
    for url in character_image_urls:
        u = _unwrap_image_url(url)
        if u and u not in unique_urls:
            unique_urls.append(u)

    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(headers=IMAGE_REQUEST_HEADERS, connector=connector) as session:
        if not unique_urls:
            return []
        unique_urls = unique_urls[:MAX_CHARACTER_IMAGES]

        fetch_tasks: list[asyncio.Task] = [
            asyncio.create_task(_fetch_image_bytes(session, url))
            for url in unique_urls
        ]
        pending: set[asyncio.Task] = set(fetch_tasks)
        loaded_images: list[bytes] = []

        for task in asyncio.as_completed(list(pending)):
            try:
                image = await task
                if image is not None:
                    loaded_images.append(image)
                    if len(loaded_images) >= MAX_CHARACTER_IMAGES:
                        break
            except Exception as exc:
                print(f"Character image task failed: {exc}", flush=True)

        for task in pending:
            if not task.done():
                task.cancel()

    return loaded_images


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
        """Generate a URL for a GCS object. Uses public URL (bucket must be public)."""
        if not gs_uri or not gs_uri.startswith("gs://"):
            return None

        # Just use public URL - signed URLs require service account key file
        # To use this, run: gsutil iam ch allUsers:objectViewer gs://YOUR_BUCKET_NAME
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
                "duration_seconds": request.duration_seconds,
                "shorts_style": request.shorts_style,
                "source_image_url": request.source_image_url,
                "character_image_urls": request.character_image_urls,
            },
        )

        job_data = {
            "title": request.title,
            "outcome": request.outcome,
            "original_bet_link": request.original_bet_link,
            "duration_seconds": request.duration_seconds,
            "shorts_style": request.shorts_style,
            "source_image_url": request.source_image_url,
            "character_image_urls": request.character_image_urls,
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
            outcome = (job_data.get("outcome") or job_data.get("caption") or "").strip()
            if not outcome:
                raise ValueError("outcome is required")
            original_bet_link = job_data["original_bet_link"]
            duration = int(job_data.get("duration_seconds", 8))
            shorts_style = normalize_shorts_style(job_data.get("shorts_style"))
            source_image_url = job_data.get("source_image_url")
            # Parse character image URLs
            raw_urls = job_data.get("character_image_urls") or []
            if isinstance(raw_urls, str):
                raw_urls = [u.strip() for u in raw_urls.replace("\r", "\n").split("\n") if u.strip()]
            character_image_urls = [u for u in raw_urls if _is_probable_url(u)]

            # Fetch source image if URL provided
            source_image = None
            if source_image_url:
                source_image = await fetch_image_from_url(source_image_url)
                if source_image:
                    print(f"[{jid}] Using source image ({len(source_image)} bytes)", flush=True)

            # Fetch character images
            character_images = []
            if character_image_urls:
                print(f"[{jid}] Fetching {len(character_image_urls)} character image(s)...", flush=True)
                character_images = await _load_character_images(
                    character_image_urls=character_image_urls,
                )
                print(f"[{jid}] Loaded {len(character_images)} character image(s)", flush=True)

            # Use provided source image directly as the Veo starting frame.
            # Fallback to Gemini start-frame generation only when source image is missing.
            if source_image:
                first_image = source_image
                print(f"[{jid}] Using source image directly as Veo starting frame", flush=True)
            else:
                first_prompt = create_first_image_prompt(
                    title=title,
                    outcome=outcome,
                    original_bet_link=original_bet_link,
                    style=shorts_style,  # "action" or "animated"
                )
                first_image = await self.vertex_service.generate_image_from_prompt(
                    prompt=first_prompt,
                )

            image_uri = ""
            if self.bucket:
                image_uri = await asyncio.to_thread(self._upload_image_sync, job_id, 1, first_image)

            veo_prompt = create_video_prompt(
                title=title,
                outcome=outcome,
                original_bet_link=original_bet_link,
                style=shorts_style,  # "action" or "animated"
            )
            operation = await self.vertex_service.generate_video_content(
                prompt=veo_prompt,
                image_data=first_image,
                character_images=character_images if character_images else None,
                duration_seconds=duration,
            )

            await self._save_job(job_id, {
                "status": "processing",
                "operation_name": operation.name,
                "job_start_time": existing_job.get("job_start_time") if existing_job else start_time,
                "title": title,
                "outcome": outcome,
                "original_bet_link": original_bet_link,
                "duration_seconds": duration,
                "shorts_style": shorts_style,
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
                "duration_seconds": int(job_data.get("duration_seconds", 8)),
                "shorts_style": normalize_shorts_style(job_data.get("shorts_style")),
            })

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Poll job status."""
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

    async def update_job(self, job_id: str, data: dict):
        existing = await self._load_job(job_id) or {}
        existing.update(data)
        await self._save_job(job_id, existing)
