def _scene_direction(title: str, outcome: str) -> str:
    """Return domain-aware scene direction for the starting frame."""
    text = f"{title} {outcome}".lower()

    if any(kw in text for kw in ("football", "nfl", "super bowl", "basketball", "nba", "soccer", "fifa", "baseball", "mlb", "hockey", "nhl", "touchdown", "dunk")):
        return """- Mid-action peak moment with motion cues (speed trails, debris, crowd reaction, dramatic body movement).
- Stadium/arena atmosphere with dramatic broadcast lighting.
- Authentic uniforms, gear, and packed crowd energy.
- Think ESPN highlight reel frozen at the most dramatic millisecond."""

    if any(kw in text for kw in ("mars", "moon", "space", "rocket", "astronaut", "nasa", "spacex", "orbit", "colonize", "launch")):
        return """- Think Interstellar or The Martian — vast, awe-inspiring, epic scale.
- Show the outcome as a breathtaking moment: astronauts on alien terrain, a spacecraft approaching a planet, a colony under construction on a barren surface, a rocket mid-launch with massive thrust plumes.
- Dramatic lighting from stars, planetary horizons, or engine glow against the void of space.
- Sense of human achievement against the enormity of the cosmos."""

    if any(kw in text for kw in ("bitcoin", "crypto", "ethereum", "stock", "nasdaq", "dow", "market", "recession", "inflation", "fed", "interest rate")):
        return """- Think The Big Short or Wall Street — high-stakes trading floor energy.
- Screens with charts everywhere, intense human reactions, city skylines or trading floors.
- Green/red lighting reflecting market mood, dramatic tension in faces and body language.
- The decisive moment of a market move captured in one frame."""

    if any(kw in text for kw in ("election", "president", "vote", "congress", "senate", "political", "campaign", "democrat", "republican")):
        return """- Election night energy — the decisive moment of victory or revelation.
- Podiums, crowds, confetti, dramatic lighting, American political imagery.
- Capture the emotion: triumph, shock, celebration — a historic moment frozen in time."""

    if any(kw in text for kw in ("hurricane", "tornado", "earthquake", "flood", "wildfire", "climate", "weather", "temperature", "drought", "snow")):
        return """- Nature documentary meets disaster film — the raw power of nature at peak intensity.
- Show the event in full force: massive storm walls, floodwaters, fire lines, cracked earth.
- Human/building scale references to convey the enormity.
- Dramatic natural lighting: storm darkness, fire glow, blizzard whiteout."""

    if any(kw in text for kw in ("ai", "artificial intelligence", "robot", "tech", "apple", "google", "tesla", "self-driving", "quantum")):
        return """- Think Ex Machina or Black Mirror — sleek, futuristic, slightly awe-inspiring.
- Clean modern environments: labs, product stages, server rooms, futuristic cityscapes.
- Technology that looks plausible and grounded, glowing screens, holographic elements.
- The pivotal moment where the tech breakthrough becomes real."""

    return f"""- Imagine this as the poster frame for a blockbuster movie about "{title}".
- Build a scene that makes the outcome feel real, dramatic, and inevitable.
- Authentic environment and subjects appropriate to the topic.
- Peak dramatic moment with cinematic lighting, real stakes, and human emotion."""


def create_first_image_prompt(
    title: str,
    outcome: str,
    original_trade_link: str,
) -> str:
    """
    Build the first-frame prompt for Gemini image generation.
    The frame should unambiguously depict the selected Kalshi outcome.
    """
    scene = _scene_direction(title=title, outcome=outcome)

    return f"""Create a single 4K cinematic start frame for an 8-second vertical short video.

TOPIC: {title}
SCENARIO TO DEPICT (must be visually true): {outcome}

PRIMARY GOAL:
- Show the described scenario as already happening right now.
- Build a high-impact, action-heavy moment, not a static portrait.

SCENE DIRECTION:
- Vertical 9:16 composition optimized for mobile shorts.
{scene}

BRANDED ATMOSPHERE (subtle, environmental — never the main focus):
- Weave in subtle branded visual elements: green line graphs trending upward on screens in the background, a "K" logo on a banner or LED board, percentage numbers (like "78%") on a scoreboard, green-lit ticker displays.
- Prefer GRAPHICAL elements (charts, arrows, logos) over text. Any text that does appear MUST be in English and limited to short numbers or single words.
- Green (#00d26a) should appear naturally in environmental lighting, LED accents, or graph lines.
- These should feel like natural parts of the environment — never overlaid UI, never the focal point.

STRICT REQUIREMENTS:
1. No plain-text watermarks, no floating UI overlays, no literal app screenshots.
2. No bland studio shots, no static posed lineup.
3. The frame must look ready to animate into a blockbuster sequence.
4. Authentic gear, environment, and subjects for the topic.

Output exactly one photorealistic image."""
