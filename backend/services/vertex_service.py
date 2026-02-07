import logging

from google import genai
from google.genai.types import (
    GenerateVideosConfig,
    GenerateVideosOperation,
    Image,
)
from models.job import JobStatus
from utils.env import settings

logger = logging.getLogger("vertex_service")
MAX_REFERENCE_IMAGES = 3


def _infer_mime_type(image_bytes: bytes) -> str:
    """Best-effort image MIME sniffing for Gemini/Veo inputs."""
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


class VertexService:
    def __init__(self):
        logger.info(f"Initializing VertexService for project={settings.GOOGLE_CLOUD_PROJECT}, location={settings.GOOGLE_CLOUD_LOCATION}")
        self.client = genai.Client(
            vertexai=True,
            project=settings.GOOGLE_CLOUD_PROJECT,
            location=settings.GOOGLE_CLOUD_LOCATION
        )
        self.bucket_name = settings.GOOGLE_CLOUD_BUCKET_NAME
        logger.info(f"VertexService initialized, output bucket: {self.bucket_name}")

    async def generate_video_content(
        self,
        prompt: str,
        image_data: bytes,
        duration_seconds: int = 8,
        reference_images: list[bytes] | None = None,
    ) -> GenerateVideosOperation:
        output_gcs_uri = f"gs://{self.bucket_name}/videos/"
        ref_payload = []
        for ref_img in (reference_images or [])[:MAX_REFERENCE_IMAGES]:
            ref_payload.append(
                {
                    "image": Image(
                        image_bytes=ref_img,
                        mime_type=_infer_mime_type(ref_img),
                    ),
                    "reference_type": "ASSET",
                }
            )
        logger.info(
            f"Calling Veo preview with source image ({len(image_data)} bytes) "
            f"and {len(ref_payload)} reference image(s)"
        )
        image_mime = _infer_mime_type(image_data)
        config_kwargs = {
            "aspect_ratio": "9:16",
            "duration_seconds": duration_seconds,
            "output_gcs_uri": output_gcs_uri,
            "negative_prompt": (
                "text, captions, subtitles, annotations, logos, low quality, static shot, slideshow, "
                "ugly, bad anatomy, extra limbs, deformed faces, identity drift, face morphing, "
                "weird physics, backwards motion, reverse playback"
            ),
            "resolution": "4k",
        }
        if ref_payload:
            config_kwargs["reference_images"] = ref_payload
        try:
            config = GenerateVideosConfig(**config_kwargs)
        except Exception as exc:
            logger.warning(f"GenerateVideosConfig does not accept resolution on this SDK build: {exc}")
            config_kwargs.pop("resolution", None)
            config = GenerateVideosConfig(**config_kwargs)

        try:
            operation = self.client.models.generate_videos(
                model="veo-3.1-generate-preview",
                prompt=prompt,
                image=Image(
                    image_bytes=image_data,
                    mime_type=image_mime,
                ),
                config=config,
            )
        except Exception as exc:
            if ref_payload:
                raise RuntimeError(
                    f"Veo request failed while using source image + reference images: {exc}"
                ) from exc
            raise
        return operation
    
    async def get_video_status(self, operation: GenerateVideosOperation) -> JobStatus:
        operation = self.client.operations.get(operation)
        if operation.done and operation.result and operation.result.generated_videos:
            return JobStatus(status="done", job_start_time=None, video_url=operation.result.generated_videos[0].video.uri)
        return JobStatus(status="waiting", job_start_time=None, video_url=None)
    
    async def get_video_status_by_name(self, operation_name: str) -> JobStatus:
        """Get video status by operation name (avoids serialization)"""
        logger.debug(f"get_video_status_by_name: Polling operation {operation_name}")
        # Create a minimal operation object with just the name since get() expects an operation object
        operation = GenerateVideosOperation(name=operation_name)
        operation = self.client.operations.get(operation)
        logger.debug(f"get_video_status_by_name: done={operation.done}")

        if operation.done:
            logger.info(f"get_video_status_by_name: Operation DONE!")

            # Check for error first
            if hasattr(operation, 'error') and operation.error:
                error_msg = str(operation.error)
                logger.error(f"get_video_status_by_name: Operation FAILED with error: {error_msg}")
                return JobStatus(status="error", job_start_time=None, video_url=None, error=f"Veo error: {error_msg}")

            if operation.result:
                logger.debug(f"get_video_status_by_name: result exists")
                if operation.result.generated_videos:
                    video_count = len(operation.result.generated_videos)
                    logger.info(f"get_video_status_by_name: {video_count} video(s) generated")
                    video_uri = operation.result.generated_videos[0].video.uri
                    logger.info(f"get_video_status_by_name: Video URI from Veo: {video_uri}")
                    return JobStatus(status="done", job_start_time=None, video_url=video_uri)
                else:
                    logger.warning(f"get_video_status_by_name: No generated_videos in result!")
                    return JobStatus(status="error", job_start_time=None, video_url=None, error="Veo completed but no video generated")
            else:
                logger.warning(f"get_video_status_by_name: No result in operation!")
                return JobStatus(status="error", job_start_time=None, video_url=None, error="Veo completed but no result returned")

        logger.debug(f"get_video_status_by_name: Still processing...")
        return JobStatus(status="waiting", job_start_time=None, video_url=None)
