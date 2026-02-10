import logging

from google import genai
from google.genai.types import (
    GenerateImagesConfig,
    GenerateVideosConfig,
    GenerateVideosOperation,
    Image,
)
from models.job import JobStatus
from utils.env import settings

logger = logging.getLogger("vertex_service")


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

    async def generate_starting_frame(self, prompt: str) -> bytes | None:
        """Generate a starting frame image using Gemini Imagen."""
        logger.info("Generating starting frame via Imagen...")
        try:
            response = self.client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=prompt,
                config=GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio="9:16",
                    output_mime_type="image/png",
                ),
            )
            if response.generated_images:
                image_bytes = response.generated_images[0].image.image_bytes
                logger.info(f"Starting frame generated ({len(image_bytes)} bytes)")
                return image_bytes
            logger.warning("Imagen returned no images")
        except Exception as exc:
            logger.error(f"Starting frame generation failed: {exc}")
        return None

    async def generate_video_content(
        self,
        prompt: str,
        image_data: bytes | None,
    ) -> GenerateVideosOperation:
        output_gcs_uri = f"gs://{self.bucket_name}/videos/"
        if image_data is None:
            raise ValueError("image_data is required for video generation")
        config_kwargs = {
            "aspect_ratio": "9:16",
            "duration_seconds": 8,
            "output_gcs_uri": output_gcs_uri,
            "negative_prompt": (
                "text, captions, subtitles, annotations, logos, low quality, static shot, slideshow, "
                "ugly, bad anatomy, extra limbs, deformed faces, identity drift, face morphing, "
                "weird physics, backwards motion, reverse playback, teleporting, time jump glitches, "
                "body interpenetration, merged players, clipping through objects, impossible collisions, "
                "random extra characters, sudden outfit changes, disappearing equipment, "
                "helmetless football players, broken sports gear continuity"
            ),
            "resolution": "1080p",
        }
        try:
            config = GenerateVideosConfig(**config_kwargs)
        except Exception as exc:
            logger.warning(f"GenerateVideosConfig does not accept resolution on this SDK build: {exc}")
            config_kwargs.pop("resolution", None)
            config = GenerateVideosConfig(**config_kwargs)

        image_mime = _infer_mime_type(image_data)
        operation = self.client.models.generate_videos(
            model="veo-3.1-generate-preview",
            prompt=prompt,
            image=Image(
                image_bytes=image_data,
                mime_type=image_mime,
            ),
            config=config,
        )
        return operation

    async def get_video_status(self, operation: GenerateVideosOperation) -> JobStatus:
        operation = self.client.operations.get(operation)
        if operation.done and operation.result and operation.result.generated_videos:
            return JobStatus(status="done", job_start_time=None, video_url=operation.result.generated_videos[0].video.uri)
        return JobStatus(status="waiting", job_start_time=None, video_url=None)

    async def get_video_status_by_name(self, operation_name: str) -> JobStatus:
        """Get video status by operation name (avoids serialization)"""
        logger.debug(f"get_video_status_by_name: Polling operation {operation_name}")
        operation = GenerateVideosOperation(name=operation_name)
        operation = self.client.operations.get(operation)
        logger.debug(f"get_video_status_by_name: done={operation.done}")

        if operation.done:
            logger.info(f"get_video_status_by_name: Operation DONE!")

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
