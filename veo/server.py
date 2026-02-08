"""Veo Video Generation Sandbox"""
import io
import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from google import genai
from google.genai import types as gt
from google.cloud import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("veo")

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
BUCKET = os.getenv("GOOGLE_CLOUD_BUCKET_NAME", "")

client = genai.Client(vertexai=True, project=PROJECT, location=LOCATION)
gcs = storage.Client() if BUCKET else None

jobs: dict = {}
sequences: dict = {}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def infer_mime(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


async def describe_image(img_bytes: bytes) -> str:
    mime = infer_mime(img_bytes)
    resp = client.models.generate_content(
        model="gemini-2.0-flash-001",
        contents=[
            gt.Part.from_bytes(data=img_bytes, mime_type=mime),
            (
                "Describe this person/subject for a video generation prompt. "
                "Focus on: clothing/uniform details (exact colors, numbers, team logos), "
                "general build (tall, athletic, stocky), posture, and expression. "
                "DO NOT include specific skin tone, hair color, facial hair details, "
                "scars, tattoos, or any features that could identify a real individual. "
                "Keep physical descriptions GENERIC — say 'athletic build' not 'fair-skinned with a ginger beard'. "
                "One dense paragraph. No headers."
            ),
        ],
    )
    return resp.text


async def enhance_prompt(user_prompt: str, descriptions: list[str]) -> str:
    desc_section = ""
    if descriptions:
        desc_section = "\n\nREFERENCE SUBJECT DESCRIPTIONS (match these EXACTLY in the video):\n" + "\n".join(
            f"- Subject {i+1}: {d}" for i, d in enumerate(descriptions)
        )

    resp = client.models.generate_content(
        model="gemini-2.0-flash-001",
        contents=[
            f"""You are an expert prompt engineer for Google Veo, the most advanced video generation AI.
You specialize in creating FAST-PACED, ACTION-PACKED video prompts.

CRITICAL — NAME SANITIZATION (DO THIS FIRST):
- You MUST replace ALL real person names with role-based labels.
- Examples: "Sam Darnold" → "the quarterback", "Jaxon Smith-Njigba" → "the wide receiver", "LeBron James" → "the forward", "Patrick Mahomes" → "Subject 1"
- Use descriptive roles ("the quarterback", "the pitcher", "the coach") or generic labels ("Subject 1", "Subject 2") — NEVER include any real first name, last name, or nickname of a real person.
- Team names, city names, and uniform descriptions are fine — just NO real people's names.

Transform this into the best possible video generation prompt.

USER REQUEST: {user_prompt}
{desc_section}

Write a vivid, high-energy cinematic prompt (200-400 words) that:

ACTION & PHYSICS (HIGHEST PRIORITY):
- Every single second must have visible, fast-paced action — NO static shots, NO slow moments
- ALL physics must be realistic: gravity pulls objects down, thrown balls follow parabolic arcs, bodies have weight and momentum
- Collisions, catches, throws must look physically plausible — objects don't float, hover, or defy gravity
- Motion blur on fast movements, realistic impact reactions, proper body mechanics
- Structure beat-by-beat with constant energy escalation across the full duration

CAMERA (must amplify the action):
- Aggressive camera moves: whip pans, quick tracking shots, low-angle hero shots, handheld shake on impacts
- Quick cuts between angles to build intensity — wide establishing shot → tight action → reaction
- Camera should FOLLOW the action, not sit still

VISUAL STYLE:
- NFL broadcast / ESPN highlight reel quality
- Stadium floodlights with dramatic rim lighting, lens flares on impacts
- Shallow DOF rack focuses between subjects, cinematic color grade
- Film grain, anamorphic bokeh, natural motion blur

SUBJECT CONSISTENCY:
- If subjects are described, reference their exact appearances and maintain them frame-to-frame
- Full uniforms/gear must stay on for the entire clip — helmets, pads, jerseys, pants
- One ball only, consistent size, realistic trajectory at all times

VIOLENCE LANGUAGE (CRITICAL — Veo rejects violent-sounding prompts):
- NEVER use: rifles, fires, bullet, explodes, explosion, violent, collision, crash, smash, slam, tackles, hit, strike, rips, tears, destroys, attack, assault, kill, bone-crushing, devastating, punishing
- INSTEAD use: sends, delivers, tight spiral, bursts, surges, sharp cut, quick juke, contact, meets, brings down, moves, beats, advance, powerful, decisive
- This is a sports video, not a war scene — keep the energy high but the language clean

RULES:
- Output ONLY the prompt text, absolutely nothing else
- Write as if describing what the camera SEES in present tense, beat by beat
- No meta-instructions, no markdown, no headers
- No text/watermarks/logos/UI overlays in the video
- NEVER describe anything static — every frame must have motion
- IMPORTANT: Reference images of the subjects have been provided alongside this prompt. The video MUST match the exact appearance of the people in the reference images — their faces, builds, skin tones, hair, and uniforms. Treat the reference images as the ground truth for how subjects look."""
        ],
    )
    return resp.text


import re

# Hardcoded word replacements applied BEFORE Gemini sanitization
_VIOLENCE_REPLACEMENTS = [
    (r"\brifles\b", "sends"), (r"\brifle\b", "send"),
    (r"\bfires\b", "delivers"), (r"\bfire\b", "deliver"),
    (r"\bbullet\b", "fast"), (r"\bbullets\b", "fast"),
    (r"\bexplodes?\b", "surges"), (r"\bexplosion\b", "burst"), (r"\bexplosive\b", "dynamic"),
    (r"\bviolent\b", "sharp"), (r"\bviolence\b", "intensity"),
    (r"\bcollision\b", "contact"), (r"\bcollisions\b", "contacts"),
    (r"\bcrash(?:es|ing)?\b", "converge"), (r"\bsmash(?:es|ing)?\b", "meet"),
    (r"\bslam(?:s|ming)?\b", "drive"), (r"\bslammed\b", "driven"),
    (r"\btackles?\b", "brings down"), (r"\btackling\b", "bringing down"),
    (r"\bhit(?:s|ting)?\b", "meet"), (r"\bstrike(?:s)?\b", "reach"),
    (r"\bstriking\b", "reaching"), (r"\bstruck\b", "met"),
    (r"\brips?\b", "moves"), (r"\bripping\b", "moving"),
    (r"\btears?\b", "cuts"), (r"\btearing\b", "cutting"),
    (r"\bdestroys?\b", "beats"), (r"\bdemolish(?:es)?\b", "outmaneuver"),
    (r"\battack(?:s|ing)?\b", "advance"), (r"\bassault(?:s|ing)?\b", "drive"),
    (r"\bkills?\b", "stops"), (r"\bmurder\b", ""),
    (r"\bannihilat\w+", "overcome"),
    (r"\bbone.?crushing\b", "powerful"), (r"\bdevastating\b", "decisive"),
    (r"\bpunishing\b", "strong"), (r"\bbrutal\b", "intense"),
    (r"\bvicious\b", "aggressive"), (r"\bferocious\b", "energetic"),
    (r"\blethal\b", "effective"), (r"\bkiller\b", "standout"),
    (r"\bdominates?\b", "controls"), (r"\bdominating\b", "controlling"),
    (r"\bforce of\b", "power of"), (r"\bwith all his might\b", "with full effort"),
    (r"\bgritty\b", "raw"), (r"\bintense action\b", "fast-paced action"),
    (r"\bdrops back hard\b", "drops back quickly"),
    (r"\bimpacts?\b", "moments of contact"),
]


def _hardcoded_sanitize(text: str) -> str:
    """Fast regex pass to replace known Veo trigger words."""
    for pattern, replacement in _VIOLENCE_REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


async def sanitize_names(prompt: str) -> str:
    """Second-pass safety net: strip real person names AND violent-sounding language."""
    # First: fast hardcoded regex pass
    prompt = _hardcoded_sanitize(prompt)

    # Second: Gemini pass for anything we missed
    resp = client.models.generate_content(
        model="gemini-2.0-flash-001",
        contents=[
            f"""You are a safety filter for Google Veo video generation AI. Veo has an EXTREMELY strict content filter that rejects anything that sounds like real-world violence, even in sports contexts.

You have TWO jobs — do both in a single rewrite:

JOB 1 — NAME SANITIZATION:
- Remove ALL real person names. Replace with role-based labels ("the quarterback", "the wide receiver", "Subject 1").
- Team names and city names are fine.

JOB 2 — MAKE EVERY WORD VEO-SAFE (CRITICAL):
Read every single word and ask: "Could this word be interpreted as describing real-world violence or harm?"
If YES, replace it with a softer sports-appropriate synonym.

Common triggers that MUST be replaced:
- Any weapon-related metaphors: "rifles", "fires", "bullet", "cannon", "bombs", "shotgun" → "sends", "delivers", "fast", "powerful", "releases"
- Any explosion/destruction words: "explodes", "detonates", "destroys", "demolishes" → "surges", "bursts", "beats", "outmaneuvers"
- Any impact/collision words: "collision", "crash", "smash", "slam", "hit", "strike", "pound" → "contact", "meets", "converges", "engages"
- Any aggression words: "violent", "vicious", "brutal", "ferocious", "savage", "punishing" → "sharp", "quick", "strong", "energetic", "decisive"
- Any harm words: "kill", "murder", "assault", "attack", "rips", "tears" → remove or use "stops", "advances", "moves", "cuts"
- Intensity modifiers: "bone-crushing", "devastating", "lethal", "deadly" → "powerful", "decisive", "effective"
- Borderline words to soften: "force", "might", "gritty", "intense", "aggressive", "hard" → "power", "effort", "raw", "dynamic", "energetic", "quick"

The result should read like a family-friendly sports broadcast description. High energy, but ZERO words that could be misread as violence.

Output ONLY the rewritten prompt — no commentary, no markdown, no explanation.

PROMPT:
{prompt}"""
        ],
    )
    return resp.text


async def sanitize_descriptions(descriptions: list[str]) -> list[str]:
    """Strip hyper-specific physical features from image descriptions to avoid Veo real-person rejection."""
    if not descriptions:
        return descriptions

    sanitized = []
    for desc in descriptions:
        resp = client.models.generate_content(
            model="gemini-2.0-flash-001",
            contents=[
                f"""Rewrite this subject description for a video generation AI. Keep uniform/clothing details but REMOVE all specific physical identifiers.

REMOVE: specific skin tone, hair color/style, facial hair, eye color, facial features, scars, tattoos, age estimates, any detail that could identify a real person.
KEEP: uniform colors, jersey numbers, team logos, helmet details, general build (tall/athletic/stocky), posture, expression type (focused/determined).

Input: {desc}

Output ONLY the rewritten description. No commentary."""
            ],
        )
        sanitized.append(resp.text)
    return sanitized


async def decompose_into_shots(scene: str, descriptions: list[str], num_shots: int = 4) -> list[dict]:
    """Use Gemini to break a complex scene into individual shot prompts for Veo."""
    desc_section = ""
    if descriptions:
        desc_section = "\n\nREFERENCE SUBJECT DESCRIPTIONS (use these for visual consistency):\n" + "\n".join(
            f"- Subject {i+1}: {d}" for i, d in enumerate(descriptions)
        )

    resp = client.models.generate_content(
        model="gemini-2.0-flash-001",
        contents=[
            f"""You are a film director breaking a complex scene into {num_shots} individual camera shots for a video generation AI (Google Veo).

SCENE: {scene}
{desc_section}

CRITICAL — NAME SANITIZATION:
- Replace ALL real person names with role-based labels ("the quarterback", "the wide receiver", "Subject 1", etc.)
- Team names and city names are fine — NO real people's names.

CRITICAL — PERSON DESCRIPTION RULES:
- NEVER use specific skin tones (e.g., "fair", "dark", "olive") — use "the quarterback" or "Subject 1" instead
- NEVER describe specific facial features (e.g., "ginger beard", "blue eyes", "sharp jawline")
- NEVER describe body-specific details (e.g., "protective padding on throwing arm", "tape on left wrist")
- DO reference uniform details: jersey color, number, helmet style, team colors
- DO reference general build: "tall athletic build", "compact powerful frame"
- Subjects should be identified by ROLE + UNIFORM, not by physical body descriptions
- This is critical: overly specific physical descriptions will cause the video AI to reject the prompt

Break this into exactly {num_shots} individual shots. Each shot will be generated as a separate video clip.

For each shot, provide:
- "shot_label": short label like "Shot 1: The Throw", "Shot 2: Ball Flight"
- "camera": camera angle/movement description
- "action": what happens in this shot
- "transition": how this shot ends and connects to the next (for the last shot, set to "final")
- "prompt": a self-contained Veo video generation prompt (150-250 words) that describes ONLY this shot. Include camera work, action, lighting, style. Must work standalone without context from other shots. Reference subjects by their ROLE and UNIFORM only (e.g., "the quarterback in the navy #14 jersey"), never by physical body features.

EDITING & TRANSITIONS (CRITICAL for stitching shots together):
- Shots 1 through {num_shots - 1}: each shot MUST end with a natural CUT POINT — a moment that visually transitions to the next shot. Examples: end on a whip pan, subject exiting frame, object filling frame, dramatic zoom-in, or motion blur moment.
- Shot {num_shots} (FINAL): must end with a CONCLUSIVE moment — a celebration, held wide shot, slow-motion freeze, or fade-to-atmosphere. This is the ending.
- In each shot's "prompt" text, explicitly describe how the shot ENDS (the last 1-2 seconds).

Output ONLY a JSON array of objects. No markdown, no commentary, no code fences.

Example format:
[{{"shot_label": "Shot 1: The Setup", "camera": "Low angle tracking", "action": "Quarterback drops back", "transition": "whip pan right following the throw", "prompt": "A cinematic low-angle tracking shot..."}}]"""
        ],
    )

    text = resp.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[: text.rfind("```")]
    text = text.strip()

    try:
        shots = json.loads(text)
    except json.JSONDecodeError:
        log.error(f"Failed to parse shot decomposition: {text[:200]}")
        raise ValueError("Gemini returned invalid JSON for shot decomposition")

    return shots


async def generate_starting_frame(prompt: str, descriptions: list[str], aspect_ratio: str) -> bytes | None:
    """Use Imagen to generate a starting frame that depicts the described subjects."""
    desc_block = "\n".join(f"- {d}" for d in descriptions)
    frame_prompt = f"""Photorealistic cinematic action still frame, {aspect_ratio} composition. Freeze-frame of peak action moment — mid-motion, dynamic poses, bodies in athletic movement, NOT a static portrait.

Scene: {prompt}

Subjects (match these appearances EXACTLY — these are real people, replicate their faces and builds):
{desc_block}

Style: NFL broadcast freeze-frame quality, stadium floodlights, dramatic rim lighting on helmets and shoulders, motion blur on extremities, shallow DOF, 4K cinematic detail, lens flare.
No text, no watermarks, no UI elements, no logos, no captions. No static poses — every subject must be mid-action."""

    log.info(f"Generating Imagen starting frame...")
    try:
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=frame_prompt[:5000],
            config=gt.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                output_mime_type="image/png",
                person_generation="ALLOW_ADULT",
            ),
        )
        if response.generated_images:
            img_bytes = response.generated_images[0].image.image_bytes
            log.info(f"Imagen frame generated ({len(img_bytes)} bytes)")
            return img_bytes
        log.warning("Imagen returned no images")
    except Exception as e:
        log.error(f"Imagen frame generation failed: {e}")
    return None


@app.get("/", response_class=HTMLResponse)
async def root():
    with open(os.path.join(os.path.dirname(__file__), "static", "index.html")) as f:
        return f.read()


@app.post("/api/generate")
async def generate(
    images: list[UploadFile] = File(default=[]),
    prompt: str = Form(...),
    aspect_ratio: str = Form("9:16"),
    duration: int = Form(8),
    model: str = Form("veo-3.1-generate-preview"),
    use_first_as_frame: bool = Form(False),
    imagen_frame: bool = Form(True),
    person_generation: str = Form("allow_adult"),
    veo_enhance: bool = Form(True),
    gemini_enhance: bool = Form(True),
    generate_audio: bool = Form(False),
    negative_prompt: str = Form(""),
):
    job_id = str(uuid.uuid4())[:8]
    log.info(f"[{job_id}] Starting: model={model} aspect={aspect_ratio} dur={duration}s")

    # Read all uploaded images
    img_list = []
    for f in images:
        data = await f.read()
        if data:
            img_list.append((data, f.filename or "image"))

    log.info(f"[{job_id}] {len(img_list)} image(s), first_as_frame={use_first_as_frame}, imagen_frame={imagen_frame}")

    # Gemini: analyze reference images + enhance prompt
    final_prompt = prompt
    descriptions = []
    if gemini_enhance and img_list:
        for img_bytes, fname in img_list:
            try:
                desc = await describe_image(img_bytes)
                descriptions.append(desc)
                log.info(f"[{job_id}] Described: {fname}")
            except Exception as e:
                log.error(f"[{job_id}] Describe failed for {fname}: {e}")
    if gemini_enhance:
        try:
            final_prompt = await enhance_prompt(prompt, descriptions)
            log.info(f"[{job_id}] Prompt enhanced")
        except Exception as e:
            log.error(f"[{job_id}] Enhancement failed, using raw prompt: {e}")

    # Second-pass name sanitization
    try:
        final_prompt = await sanitize_names(final_prompt)
        log.info(f"[{job_id}] Names sanitized")
    except Exception as e:
        log.error(f"[{job_id}] Name sanitization failed, continuing: {e}")

    # Veo requires 8s duration when reference images are used (no starting frame)
    if img_list and not imagen_frame and duration != 8:
        log.info(f"[{job_id}] Overriding duration {duration}s → 8s (required with reference images)")
        duration = 8

    # Starting frame: Imagen-generated (default) > uploaded first image > none
    frame_data = None
    if imagen_frame and (descriptions or prompt):
        frame_data = await generate_starting_frame(final_prompt, descriptions, aspect_ratio)
        if frame_data:
            log.info(f"[{job_id}] Imagen starting frame ready")
        else:
            log.warning(f"[{job_id}] Imagen frame failed, falling back")

    if not frame_data and use_first_as_frame and img_list:
        frame_data = img_list[0][0]
        log.info(f"[{job_id}] Using uploaded image as starting frame")

    # Build config
    config_kwargs: dict = {
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration,
        "person_generation": person_generation.upper(),
        "enhance_prompt": veo_enhance,
        "generate_audio": generate_audio,
        "resolution": "4k",
    }

    if negative_prompt.strip():
        config_kwargs["negative_prompt"] = negative_prompt.strip()

    if BUCKET:
        config_kwargs["output_gcs_uri"] = f"gs://{BUCKET}/veo-sandbox/{job_id}/"

    # Veo API: cannot use image + reference_images together
    # If we have an Imagen starting frame, skip reference_images (subjects are already in the frame)
    # If no starting frame, attach reference_images so Veo has subject context
    if not frame_data and img_list:
        config_kwargs["reference_images"] = [
            gt.VideoGenerationReferenceImage(
                image=gt.Image(image_bytes=ib, mime_type=infer_mime(ib)),
                reference_type="ASSET",
            )
            for ib, _ in img_list
        ]
        log.info(f"[{job_id}] {len(img_list)} reference image(s) attached (no starting frame)")
    elif frame_data:
        log.info(f"[{job_id}] Using Imagen frame — skipping reference_images (API doesn't allow both)")

    config = gt.GenerateVideosConfig(**config_kwargs)

    # Build Veo request
    veo_kwargs: dict = {"model": model, "prompt": final_prompt, "config": config}
    if frame_data:
        veo_kwargs["image"] = gt.Image(image_bytes=frame_data, mime_type=infer_mime(frame_data))
        log.info(f"[{job_id}] Starting frame attached to Veo")

    log.info(f"[{job_id}] Submitting to Veo...")
    try:
        operation = client.models.generate_videos(**veo_kwargs)
    except Exception as e:
        log.error(f"[{job_id}] Veo submit failed: {e}")
        raise HTTPException(500, str(e))

    jobs[job_id] = {
        "op": operation.name,
        "status": "processing",
        "prompt": final_prompt,
        "descriptions": descriptions,
        "model": model,
    }

    log.info(f"[{job_id}] Operation: {operation.name}")
    return {
        "job_id": job_id,
        "operation_name": operation.name,
        "enhanced_prompt": final_prompt,
        "descriptions": descriptions,
    }


@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    try:
        op = gt.GenerateVideosOperation(name=job["op"])
        op = client.operations.get(op)

        if op.done:
            if hasattr(op, "error") and op.error:
                job["status"] = "error"
                return {"status": "error", "error": str(op.error)}

            if op.result and op.result.generated_videos:
                video = op.result.generated_videos[0].video
                if video.uri:
                    job["status"] = "done"
                    job["video_uri"] = video.uri
                    return {"status": "done", "video_url": f"/api/video/{job_id}"}
                if hasattr(video, "video_bytes") and video.video_bytes:
                    job["status"] = "done"
                    job["video_bytes"] = video.video_bytes
                    return {"status": "done", "video_url": f"/api/video/{job_id}"}

            job["status"] = "error"
            return {"status": "error", "error": "Completed but no video in result"}

        return {"status": "processing"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/api/video/{job_id}")
async def get_video(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    if "video_uri" in job:
        uri = job["video_uri"]
        path = uri.replace("gs://", "")
        bucket_name = path.split("/")[0]
        blob_path = "/".join(path.split("/")[1:])
        try:
            bucket = gcs.bucket(bucket_name)
            blob = bucket.blob(blob_path)
            data = blob.download_as_bytes()
            return StreamingResponse(
                io.BytesIO(data),
                media_type="video/mp4",
                headers={"Content-Disposition": f'inline; filename="veo-{job_id}.mp4"'},
            )
        except Exception as e:
            raise HTTPException(500, f"GCS download failed: {e}")

    if "video_bytes" in job:
        return StreamingResponse(
            io.BytesIO(job["video_bytes"]),
            media_type="video/mp4",
            headers={"Content-Disposition": f'inline; filename="veo-{job_id}.mp4"'},
        )

    raise HTTPException(404, "Video not ready")


@app.post("/api/director")
async def director(
    images: list[UploadFile] = File(default=[]),
    prompt: str = Form(...),
    aspect_ratio: str = Form("9:16"),
    duration_per_shot: int = Form(8),
    num_shots: int = Form(4),
    model: str = Form("veo-3.1-generate-preview"),
    person_generation: str = Form("allow_adult"),
    veo_enhance: bool = Form(True),
    gemini_enhance: bool = Form(True),
    generate_audio: bool = Form(False),
    negative_prompt: str = Form(""),
):
    seq_id = str(uuid.uuid4())[:8]
    log.info(f"[seq-{seq_id}] Director mode: {num_shots} shots @ {duration_per_shot}s each")

    # Read uploaded images
    img_list = []
    for f in images:
        data = await f.read()
        if data:
            img_list.append((data, f.filename or "image"))

    # Describe reference images
    descriptions = []
    if gemini_enhance and img_list:
        for img_bytes, fname in img_list:
            try:
                desc = await describe_image(img_bytes)
                descriptions.append(desc)
                log.info(f"[seq-{seq_id}] Described: {fname}")
            except Exception as e:
                log.error(f"[seq-{seq_id}] Describe failed for {fname}: {e}")

    # Veo requires 8s duration when reference images are used
    if img_list and duration_per_shot != 8:
        log.info(f"[seq-{seq_id}] Overriding duration {duration_per_shot}s → 8s (required with reference images)")
        duration_per_shot = 8

    # Pre-sanitize the raw user prompt before decomposition
    clean_prompt = _hardcoded_sanitize(prompt)
    try:
        clean_prompt = await sanitize_names(clean_prompt)
        log.info(f"[seq-{seq_id}] Raw prompt pre-sanitized")
    except Exception as e:
        log.error(f"[seq-{seq_id}] Pre-sanitization failed: {e}")

    # Sanitize descriptions to remove real-person triggers
    try:
        descriptions = await sanitize_descriptions(descriptions)
        log.info(f"[seq-{seq_id}] Descriptions sanitized for Veo safety")
    except Exception as e:
        log.error(f"[seq-{seq_id}] Description sanitization failed: {e}")

    # Decompose scene into shots
    try:
        shots = await decompose_into_shots(clean_prompt, descriptions, num_shots)
        log.info(f"[seq-{seq_id}] Decomposed into {len(shots)} shots")
    except Exception as e:
        log.error(f"[seq-{seq_id}] Shot decomposition failed: {e}")
        raise HTTPException(500, f"Shot decomposition failed: {e}")

    # Submit each shot as a separate Veo generation
    shot_jobs = []
    for i, shot in enumerate(shots):
        shot_prompt = shot.get("prompt", "")

        # Sanitize names from each shot prompt
        shot_prompt = _hardcoded_sanitize(shot_prompt)
        try:
            shot_prompt = await sanitize_names(shot_prompt)
        except Exception as e:
            log.error(f"[seq-{seq_id}] Shot {i} sanitization failed: {e}")

        job_id = str(uuid.uuid4())[:8]
        log.info(f"[seq-{seq_id}] Shot {i} ({job_id}): {shot.get('shot_label', '')}")
        log.info(f"[seq-{seq_id}] Shot {i} FINAL PROMPT: {shot_prompt[:300]}")

        # Build config for this shot
        config_kwargs: dict = {
            "aspect_ratio": aspect_ratio,
            "duration_seconds": duration_per_shot,
            "person_generation": person_generation.upper(),
            "enhance_prompt": veo_enhance,
            "generate_audio": generate_audio,
            "resolution": "4k",
        }

        if negative_prompt.strip():
            config_kwargs["negative_prompt"] = negative_prompt.strip()

        if BUCKET:
            config_kwargs["output_gcs_uri"] = f"gs://{BUCKET}/veo-sandbox/{job_id}/"

        # Attach reference images for subject consistency
        if img_list:
            config_kwargs["reference_images"] = [
                gt.VideoGenerationReferenceImage(
                    image=gt.Image(image_bytes=ib, mime_type=infer_mime(ib)),
                    reference_type="ASSET",
                )
                for ib, _ in img_list
            ]

        config = gt.GenerateVideosConfig(**config_kwargs)
        veo_kwargs: dict = {"model": model, "prompt": shot_prompt, "config": config}

        try:
            operation = client.models.generate_videos(**veo_kwargs)
            jobs[job_id] = {
                "op": operation.name,
                "status": "processing",
                "prompt": shot_prompt,
                "descriptions": descriptions,
                "model": model,
            }
            shot_jobs.append({
                "job_id": job_id,
                "shot_label": shot.get("shot_label", f"Shot {i+1}"),
                "camera": shot.get("camera", ""),
                "action": shot.get("action", ""),
                "prompt": shot_prompt,
                "operation_name": operation.name,
            })
            log.info(f"[seq-{seq_id}] Shot {i} submitted: {operation.name}")
        except Exception as e:
            log.error(f"[seq-{seq_id}] Shot {i} submit failed: {e}")
            shot_jobs.append({
                "job_id": job_id,
                "shot_label": shot.get("shot_label", f"Shot {i+1}"),
                "camera": shot.get("camera", ""),
                "action": shot.get("action", ""),
                "prompt": shot_prompt,
                "error": str(e),
            })

    sequences[seq_id] = {
        "status": "processing",
        "shots": shot_jobs,
        "model": model,
    }

    return {
        "sequence_id": seq_id,
        "shots": shot_jobs,
    }


@app.get("/api/sequence/{seq_id}")
async def get_sequence(seq_id: str):
    seq = sequences.get(seq_id)
    if not seq:
        raise HTTPException(404, "Sequence not found")

    all_done = True
    any_error = False

    for shot in seq["shots"]:
        # Skip shots that already finished
        if shot.get("status") in ("done", "error"):
            if shot.get("status") == "error":
                any_error = True
            continue

        job_id = shot["job_id"]
        job = jobs.get(job_id)
        if not job:
            shot["status"] = "error"
            shot["error"] = "Job not found"
            any_error = True
            continue

        if "error" in shot and "operation_name" not in shot:
            shot["status"] = "error"
            any_error = True
            continue

        try:
            op = gt.GenerateVideosOperation(name=job["op"])
            op = client.operations.get(op)

            if op.done:
                if hasattr(op, "error") and op.error:
                    job["status"] = "error"
                    shot["status"] = "error"
                    shot["error"] = str(op.error)
                    any_error = True
                elif op.result and op.result.generated_videos:
                    video = op.result.generated_videos[0].video
                    if video.uri:
                        job["status"] = "done"
                        job["video_uri"] = video.uri
                        shot["status"] = "done"
                        shot["video_url"] = f"/api/video/{job_id}"
                    elif hasattr(video, "video_bytes") and video.video_bytes:
                        job["status"] = "done"
                        job["video_bytes"] = video.video_bytes
                        shot["status"] = "done"
                        shot["video_url"] = f"/api/video/{job_id}"
                    else:
                        job["status"] = "error"
                        shot["status"] = "error"
                        shot["error"] = "No video in result"
                        any_error = True
                else:
                    job["status"] = "error"
                    shot["status"] = "error"
                    shot["error"] = "No video in result"
                    any_error = True
            else:
                all_done = False
        except Exception as e:
            shot["status"] = "error"
            shot["error"] = str(e)
            any_error = True

    if all_done:
        seq["status"] = "error" if any_error else "done"
    else:
        seq["status"] = "processing"

    return {
        "sequence_id": seq_id,
        "status": seq["status"],
        "shots": [
            {
                "job_id": s["job_id"],
                "shot_label": s.get("shot_label", ""),
                "status": s.get("status", "processing"),
                "video_url": s.get("video_url"),
                "prompt": s.get("prompt", ""),
                "error": s.get("error"),
            }
            for s in seq["shots"]
        ],
    }


@app.post("/api/stitch/{seq_id}")
async def stitch_sequence(seq_id: str):
    """Concatenate all completed shots in a sequence into one video using ffmpeg."""
    seq = sequences.get(seq_id)
    if not seq:
        raise HTTPException(404, "Sequence not found")

    # Collect video data for all completed shots, in order
    video_parts = []
    for i, shot in enumerate(seq["shots"]):
        job_id = shot.get("job_id")
        job = jobs.get(job_id)
        if not job or job.get("status") != "done":
            continue

        if "video_uri" in job:
            uri = job["video_uri"]
            path = uri.replace("gs://", "")
            bucket_name = path.split("/")[0]
            blob_path = "/".join(path.split("/")[1:])
            try:
                bucket = gcs.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                data = blob.download_as_bytes()
                video_parts.append((i, data))
            except Exception as e:
                log.error(f"[stitch-{seq_id}] Failed to download shot {i}: {e}")
        elif "video_bytes" in job:
            video_parts.append((i, job["video_bytes"]))

    if len(video_parts) < 2:
        raise HTTPException(400, f"Need at least 2 completed shots to stitch, got {len(video_parts)}")

    tmp_dir = tempfile.mkdtemp(prefix=f"veo-stitch-{seq_id}-")
    concat_list_path = os.path.join(tmp_dir, "concat.txt")
    output_path = os.path.join(tmp_dir, "stitched.mp4")

    try:
        for idx, data in video_parts:
            part_path = os.path.join(tmp_dir, f"shot_{idx}.mp4")
            with open(part_path, "wb") as f:
                f.write(data)

        with open(concat_list_path, "w") as f:
            for idx, _ in video_parts:
                f.write(f"file 'shot_{idx}.mp4'\n")

        # Try fast concat (no re-encode)
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list_path, "-c", "copy",
            "-movflags", "+faststart", output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            log.warning(f"[stitch-{seq_id}] concat copy failed, re-encoding: {result.stderr[:200]}")
            cmd_reencode = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list_path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart", output_path,
            ]
            result = subprocess.run(cmd_reencode, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                raise HTTPException(500, f"ffmpeg failed: {result.stderr[:500]}")

        with open(output_path, "rb") as f:
            stitched_bytes = f.read()

        stitch_id = f"stitch-{seq_id}"
        jobs[stitch_id] = {
            "op": "local-stitch",
            "status": "done",
            "video_bytes": stitched_bytes,
            "model": "ffmpeg-concat",
        }

        log.info(f"[stitch-{seq_id}] Stitched {len(video_parts)} shots, {len(stitched_bytes)} bytes")
        return {
            "stitch_id": stitch_id,
            "video_url": f"/api/video/{stitch_id}",
            "shots_included": len(video_parts),
        }

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.get("/api/jobs")
async def list_jobs():
    return {
        jid: {"status": j["status"], "model": j.get("model"), "op": j["op"]}
        for jid, j in jobs.items()
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
