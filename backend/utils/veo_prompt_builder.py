def create_video_prompt(
    title: str,
    outcome: str,
    original_bet_link: str,
    style: str = "action",
) -> str:
    """
    Build the Veo prompt for video generation.
    style: "action" (realistic) or "animated" (2D stylized)
    """

    # Logic constraints to prevent AI nonsense
    logic_rules = """
LOGIC RULES (CRITICAL - MAINTAIN THROUGHOUT VIDEO):
- Characters must stay consistent - same face, same clothes, same equipment
- If football: helmets stay ON during gameplay, never disappear
- If showing a real person, they must remain recognizable
- Physics must be realistic - no floating, no teleporting
- Equipment and uniforms do not change or vanish
- Follow the actual rules of the sport/activity shown
- No random cuts to unrelated scenes
"""

    if style == "animated":
        return f"""Animate this frame into an 8-second stylized 2D animation video.

SCENARIO: {title}
OUTCOME: {outcome}

ANIMATION STYLE:
- Maintain the 2D animated aesthetic throughout
- Smooth, fluid motion like anime or Pixar
- Can have stylized effects (speed lines, sparkles)
- Keep characters recognizable and consistent

{logic_rules}

SEQUENCE:
0-3s: Action builds
3-6s: Peak moment
6-8s: Resolution/celebration

NO text or UI overlays. Keep it visually cohesive."""

    # Default: action/realistic
    return f"""Animate this frame into an 8-second realistic sports/action video.

SCENARIO: {title}
OUTCOME: {outcome}

STYLE:
- ESPN highlight reel quality
- Realistic motion and physics
- Broadcast camera angles
- Natural athletic movement

{logic_rules}

SEQUENCE:
0-3s: Action in progress
3-6s: Key moment (can use slight slow-mo)
6-8s: Reaction/celebration

NO text or UI overlays. Make it feel like real broadcast footage."""
