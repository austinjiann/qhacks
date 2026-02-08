def _domain_specific_rules(title: str, outcome: str) -> str:
    text = f"{title} {outcome}".lower()

    if any(
        kw in text
        for kw in (
            "football",
            "nfl",
            "touchdown",
            "quarterback",
            "linebacker",
            "running back",
            "super bowl",
            "field goal",
        )
    ):
        return """- American football continuity is mandatory: every active player wears helmet (with facemask/chinstrap), shoulder pads, jersey, and pants for the full clip.
- Team identity must stay stable by uniform colors and player role; no random swaps, clones, or merged bodies.
- Use exactly one football with consistent shape/size; ball movement must follow a continuous, physically plausible arc.
- Tackles/blocks/collisions must respect body boundaries; no clipping, interpenetration, or impossible joint bends."""

    if any(
        kw in text
        for kw in ("basketball", "nba", "dunk", "three-pointer", "free throw")
    ):
        return """- Basketball continuity is mandatory: one ball only, correct court context, and stable team uniforms.
- Dribbles, passes, and shots must be physically plausible with uninterrupted ball trajectory and gravity.
- Players must not overlap through each other, fuse together, or teleport across the court."""

    if any(
        kw in text
        for kw in ("soccer", "fifa", "football match", "goalkeeper", "penalty kick")
    ):
        return """- Soccer continuity is mandatory: one match ball, stable team kits, and realistic field play.
- Foot-to-ball contact and shot direction must be physically plausible; no sudden ball shape/size changes.
- Players cannot clip through each other or phase through the ball."""

    return """- Keep all visible rules of the scene internally consistent from start to end.
- Wardrobe, tools, vehicles, and environment props must remain appropriate to the activity and cannot randomly appear/disappear.
- Bodies and objects must obey collision boundaries (no clipping, merging, or interpenetration)."""


def create_video_prompt(
    title: str,
    outcome: str,
    original_bet_link: str,
) -> str:
    """
    Build a high-quality Veo prompt for an 8-second vertical clip.
    """
    domain_rules = _domain_specific_rules(title=title, outcome=outcome)

    return f"""Create an 8-second vertical cinematic video from the provided start frame.

BET TOPIC: {title}
REQUIRED OUTCOME: {outcome}
MARKET CONTEXT: {original_bet_link}

GOAL:
- Clearly show that the required outcome is true.
- Keep continuity with the source image and provided reference images.
- Keep characters and uniforms consistent across the clip.

HARD CONSTRAINTS (HIGHEST PRIORITY):
- Follow real-world physics: momentum, gravity, contact, and inertia must be believable.
- No impossible motion: no teleporting, time jumps, reverse playback, or sudden scene mutations.
- Preserve identity and count consistency for all key subjects from first frame to final frame.
- Actions must remain causal and logical; each frame should follow naturally from the previous frame.
{domain_rules}

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
- If style conflicts with logic, prioritize logic and realism.

OUTPUT RULES:
- Vertical 9:16 composition.
- No text, captions, logos, subtitles, UI, or watermarks.
- No identity drift, no face morphing, no unrelated extra subjects."""
