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

    if any(
        kw in text
        for kw in ("mars", "moon", "space", "rocket", "astronaut", "nasa", "spacex", "orbit", "colonize", "launch")
    ):
        return """- Treat this like a scene from Interstellar or The Martian — epic scale, awe-inspiring visuals.
- Space physics: zero-g movement outside atmosphere, realistic thrust plumes, no sound-in-vacuum cheating on visuals.
- Spacecraft, suits, and habitats must stay consistent in design and detail throughout the clip.
- Planetary surfaces must feel real: dust, terrain texture, horizon curvature, atmospheric haze appropriate to the body."""

    if any(
        kw in text
        for kw in ("bitcoin", "crypto", "ethereum", "stock", "s&p", "nasdaq", "dow", "market crash", "recession", "inflation", "fed", "interest rate")
    ):
        return """- Treat this like a scene from The Big Short or Margin Call — high-stakes trading floor energy.
- Screens with green/red charts, ticker boards, intense human reactions to market moves.
- Environment: trading floors, financial districts, screens everywhere, city skylines.
- Keep chart movements and number changes physically consistent — no random jumps."""

    if any(
        kw in text
        for kw in ("election", "president", "vote", "congress", "senate", "governor", "political", "democrat", "republican", "campaign")
    ):
        return """- Treat this like a scene from election night coverage — crowds, podiums, confetti, dramatic reveals.
- Rally/debate/victory atmosphere with authentic American political imagery.
- Crowd reactions must be consistent — no teleporting people, no sudden mood flips.
- Flags, banners, and stage setups must stay stable throughout."""

    if any(
        kw in text
        for kw in ("weather", "hurricane", "tornado", "earthquake", "flood", "temperature", "snow", "drought", "wildfire", "climate")
    ):
        return """- Treat this like a scene from a disaster movie or nature documentary — raw power of nature on display.
- Weather effects must be physically consistent: wind direction, water flow, debris paths all coherent.
- Scale must feel real — show the enormity through human/building reference points.
- Lighting should match the weather: dark storm clouds, fire glow, blizzard whiteout, etc."""

    if any(
        kw in text
        for kw in ("ai", "artificial intelligence", "robot", "tech", "apple", "google", "tesla", "self-driving", "quantum")
    ):
        return """- Treat this like a scene from Ex Machina or a Black Mirror episode — sleek, futuristic, slightly awe-inspiring.
- Technology should look plausible and grounded, not cartoonish sci-fi.
- Clean modern environments: labs, server rooms, product stages, futuristic cityscapes.
- Screens and interfaces should animate smoothly with consistent design language."""

    return """- Imagine this as a pivotal scene from a blockbuster movie about this exact topic.
- Build a world that feels real and grounded — authentic environments, plausible action, real stakes.
- Wardrobe, tools, vehicles, and environment props must remain appropriate to the activity and cannot randomly appear/disappear.
- Bodies and objects must obey collision boundaries (no clipping, merging, or interpenetration)."""


def _domain_style(title: str, outcome: str) -> str:
    """Return the right cinematic style reference for this topic."""
    text = f"{title} {outcome}".lower()

    if any(kw in text for kw in ("football", "nfl", "super bowl", "basketball", "nba", "soccer", "fifa", "baseball", "mlb", "hockey", "nhl")):
        return "Sports-broadcast and trailer-level intensity."

    if any(kw in text for kw in ("mars", "moon", "space", "rocket", "astronaut", "nasa", "spacex", "orbit", "colonize", "launch")):
        return "Interstellar / The Martian epic sci-fi cinematography — vast scale, orchestral intensity, awe and wonder."

    if any(kw in text for kw in ("bitcoin", "crypto", "stock", "nasdaq", "market", "recession", "inflation", "fed")):
        return "The Big Short / Wall Street intensity — fast cuts, tension, high-stakes energy."

    if any(kw in text for kw in ("election", "president", "vote", "congress", "political", "campaign")):
        return "Election night drama — anticipation, crowd energy, historic-moment gravitas."

    if any(kw in text for kw in ("hurricane", "tornado", "earthquake", "flood", "wildfire", "climate", "weather")):
        return "Nature documentary meets disaster film — raw power, stunning scale, visceral impact."

    if any(kw in text for kw in ("ai", "artificial intelligence", "robot", "tech", "tesla", "quantum")):
        return "Sleek sci-fi thriller cinematography — Ex Machina / Black Mirror vibes, clean and futuristic."

    return "Blockbuster movie trailer intensity — dramatic, grounded, real stakes."


def create_video_prompt(
    title: str,
    outcome: str,
    original_trade_link: str,
) -> str:
    """
    Build a high-quality Veo prompt for an 8-second vertical clip.
    """
    domain_rules = _domain_specific_rules(title=title, outcome=outcome)
    style = _domain_style(title=title, outcome=outcome)

    return f"""Create an 8-second vertical cinematic video from the provided start frame.

TOPIC: {title}
SCENARIO TO DEPICT: {outcome}

GOAL:
- Clearly show that the described scenario is happening.
- Keep continuity with the source image used as the starting frame.
- Keep characters, objects, and environments consistent across the clip.

HARD CONSTRAINTS (HIGHEST PRIORITY):
- Follow real-world physics: momentum, gravity, contact, and inertia must be believable.
- No impossible motion: no teleporting, time jumps, reverse playback, or sudden scene mutations.
- Preserve identity and count consistency for all key subjects from first frame to final frame.
- Actions must remain causal and logical; each frame should follow naturally from the previous frame.
{domain_rules}

BRANDED ATMOSPHERE (subtle, environmental — never the main focus):
- Maintain any branded elements from the start frame: green line graphs on screens, "K" logos on banners, percentage numbers on scoreboards, green LED accents.
- These elements should animate naturally (graphs tick upward, banners sway, LEDs pulse) — never freeze or pop in/out.
- Prefer graphical elements (charts, arrows, logos) over words. Any visible text MUST be in English only — keep it to short numbers or single words.
- They must stay background dressing, never compete with the main action.

QUALITY TARGET:
- Premium cinematic quality, high detail, realistic textures, and dramatic lighting.
- Dynamic camera motion with clean composition.
- Natural motion blur and coherent subject movement.

SHOT STRUCTURE (8s):
- 0.0-2.5s: establish scene, pace, and stakes.
- 2.5-5.5s: decisive action that proves the scenario.
- 5.5-8.0s: payoff reaction and clear final confirmation.

STYLE RULES:
- {style}
- Realistic physics and continuity.
- No reverse motion, no static slideshow look.
- If style conflicts with logic, prioritize logic and realism.

OUTPUT RULES:
- Vertical 9:16 composition.
- No floating UI overlays, no literal app screenshots, no plain-text watermarks.
- No identity drift, no face morphing, no unrelated extra subjects."""
