def create_video_prompt(
    title: str,
    outcome: str,
    original_bet_link: str,
) -> str:
    """
    Build a high-quality Veo prompt for an 8-second vertical clip.
    """
    return f"""Create an 8-second vertical cinematic video from the provided start frame.

BET TOPIC: {title}
REQUIRED OUTCOME: {outcome}
MARKET CONTEXT: {original_bet_link}

GOAL:
- Clearly show that the required outcome is true.
- Keep continuity with the source image and provided reference images.
- Keep characters and uniforms consistent across the clip.

QUALITY TARGET:
- Premium cinematic quality, high detail, realistic textures, and dramatic lighting.
- Dynamic camera motion with clean composition.
- Natural motion blur and coherent subject movement.

SHOT STRUCTURE (8s):
- 0.0-2.5s: establish scene, pace, and stakes.
- 2.5-5.5s: decisive action that proves the outcome.
- 5.5-8.0s: payoff reaction and clear final confirmation.

STYLE RULES:
- Sports-broadcast and trailer-level intensity.
- Realistic physics and continuity.
- No reverse motion, no static slideshow look.

OUTPUT RULES:
- Vertical 9:16 composition.
- No text, captions, logos, subtitles, UI, or watermarks.
- No identity drift, no face morphing, no unrelated extra subjects."""
