import logging

from google import genai
from google.genai.types import (
    GenerateVideosConfig,
    GenerateVideosOperation,
    Image,
    GenerateContentConfig,
    ImageConfig,
    Part,
)
from models.job import JobStatus
from utils.env import settings

logger = logging.getLogger("vertex_service")

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

    async def generate_video_content(self, prompt: str, image_data: bytes, duration_seconds: int = 8) -> GenerateVideosOperation:
        output_gcs_uri = f"gs://{self.bucket_name}/videos/"
        operation = self.client.models.generate_videos(
            model="veo-3.1-fast-generate-001",
            prompt=prompt,
            image=Image(
                image_bytes=image_data,
                mime_type="image/png",
            ),
            config=GenerateVideosConfig(
                aspect_ratio="9:16",
                duration_seconds=duration_seconds,
                output_gcs_uri=output_gcs_uri,
                negative_prompt="text, captions, subtitles, annotations, low quality, static, ugly, weird physics, backwards motion",
            ),
        )
        return operation
    
    async def generate_image_from_prompt(
        self,
        prompt: str,
        image: bytes | None = None,
    ) -> bytes:
        if not prompt:
            raise ValueError("prompt is required")

        if image:
            # Image-to-image - this is 8-10 seconds LATER in the action
            enhanced_prompt = f"""{prompt}

This is 10 SECONDS LATER. Show what happens AFTER the action:
- Same subject but COMPLETELY DIFFERENT moment
- If someone was running, show them celebrating
- If something was building up, show the explosion/climax
- Different camera angle, different pose, different energy
- This is the RESULT of the action, not the action itself"""
            contents = [
                Part.from_bytes(data=image, mime_type="image/png"),
                enhanced_prompt,
            ]
        else:
            # Text-to-image - the opening action shot
            enhanced_prompt = f"""{prompt}

Create the opening action shot - the moment BEFORE the climax:
- High energy, mid-action
- Something is about to happen
- Photorealistic sports/news photography style"""
            contents = [enhanced_prompt]

        response = self.client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=contents,
            config=GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=ImageConfig(
                    aspect_ratio="9:16",
                ),
                candidate_count=1,
            ),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            raise Exception(str(response))

        return response.candidates[0].content.parts[0].inline_data.data

    async def generate_image_content(
        self,
        title: str,
        caption: str,
        additional: str | None = None,
        image: bytes | None = None
    ) -> bytes:
        prompt = f"{title}\n{caption}"
        if additional:
            prompt += f"\n{additional}"
        return await self.generate_image_from_prompt(prompt=prompt, image=image)
    
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
