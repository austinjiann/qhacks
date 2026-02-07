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
        character_images: list[bytes] | None = None,
    ) -> GenerateVideosOperation:
        output_gcs_uri = f"gs://{self.bucket_name}/videos/"

        logger.info(f"Calling Veo with 1 start image ({len(image_data)} bytes)")
        image_mime = _infer_mime_type(image_data)

        model_id = "veo-3.1-fast-generate-001"
        effective_duration_seconds = duration_seconds
        aspect_ratio = "9:16"
        prompt_for_video = prompt
        config_kwargs: dict = {
            "aspect_ratio": aspect_ratio,
            "duration_seconds": effective_duration_seconds,
            "output_gcs_uri": output_gcs_uri,
            "negative_prompt": (
                "text, captions, subtitles, annotations, logos, low quality, static shot, slideshow, "
                "ugly, bad anatomy, extra limbs, deformed faces, identity drift, face morphing, "
                "weird physics, backwards motion, reverse playback"
            ),
        }

        # Direct subject/character reference mode requires preview model.
        if character_images:
            model_id = "veo-3.1-generate-preview"
            effective_duration_seconds = 8
            # Veo 3.1 preview reference-image mode supports 16:9 only.
            aspect_ratio = "16:9"

            limited_refs = character_images[:3]
            if len(character_images) > 3:
                logger.info(
                    "Veo reference-image mode supports up to 3 assets; truncating from %s to 3",
                    len(character_images),
                )

            reference_images = [
                {
                    "image": Image(
                        image_bytes=ref,
                        mime_type=_infer_mime_type(ref),
                    ),
                    "reference_type": "asset",
                }
                for ref in limited_refs
            ]
            config_kwargs["reference_images"] = reference_images
            config_kwargs["duration_seconds"] = effective_duration_seconds
            config_kwargs["aspect_ratio"] = aspect_ratio
            prompt_for_video = (
                f"""{prompt}

REFERENCE MODE CONSTRAINT:
- Keep key action and subjects in the center-safe area for potential 9:16 crop in post."""
            )
            logger.info(
                "Using Veo preview reference-image mode with %s direct character asset(s), aspect=%s, duration=%ss",
                len(limited_refs),
                aspect_ratio,
                effective_duration_seconds,
            )

        operation = self.client.models.generate_videos(
            model=model_id,
            prompt=prompt_for_video,
            image=Image(
                image_bytes=image_data,
                mime_type=image_mime,
            ),
            config=GenerateVideosConfig(**config_kwargs),
        )
        return operation
    
    async def generate_image_from_prompt(
        self,
        prompt: str,
        image: bytes | None = None,
        character_images: list[bytes] | None = None,
    ) -> bytes:
        if not prompt:
            raise ValueError("prompt is required")

        contents = []

        # Add source image first if provided
        if image:
            logger.info(f"Adding source image ({len(image)} bytes) to Gemini request")
            contents.append(Part.from_bytes(data=image, mime_type=_infer_mime_type(image)))

        # Add character images for identity context
        if character_images:
            logger.info(f"Adding {len(character_images)} character image(s) to Gemini request")
            for i, ref_img in enumerate(character_images):
                logger.info(f"  Character image {i+1}: {len(ref_img)} bytes")
                contents.append(Part.from_bytes(data=ref_img, mime_type=_infer_mime_type(ref_img)))
        else:
            logger.info("No character images provided to Gemini")

        # Build strict image-conditioning instructions based on supplied images.
        if image and character_images:
            enhanced_prompt = f"""{prompt}

IMAGE USAGE INSTRUCTIONS:
- IMAGE 1 is the ACTION AND COMPOSITION anchor.
- IMAGES 2+ are CHARACTER IDENTITY anchors.

HARD CONSTRAINTS:
- Faces from IMAGES 2+ must match exactly (facial structure, skin tone, hairline, age range).
- Do not merge identities, swap faces, or invent new primary subjects.
- Keep each character as a distinct person on screen (no blended faces).
- Keep uniform/team styling from IMAGE 1 when visible.
- Preserve high-energy motion pose from IMAGE 1.
- Scene must clearly depict the selected outcome as true."""
        elif image:
            enhanced_prompt = f"""{prompt}

Use the provided action image as reference for:
- Athletic pose and composition
- Uniform colors and team branding
- Energy and movement style
- Stadium atmosphere

Create a cinematic, action-heavy frame that can cleanly animate into an intense short clip."""
        elif character_images:
            enhanced_prompt = f"""{prompt}

The provided images are CHARACTER references.
- Use all provided identities as the main subjects.
- Faces must match exactly.
- Build a dynamic scene around these people.
- No face morphing, no identity swaps."""
        else:
            enhanced_prompt = prompt

        contents.append(enhanced_prompt)

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
        outcome: str,
        additional: str | None = None,
        image: bytes | None = None
    ) -> bytes:
        prompt = f"{title}\n{outcome}"
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
