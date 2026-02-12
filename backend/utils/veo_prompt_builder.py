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


def _domain_palette(title: str, outcome: str) -> str:
    text = f"{title} {outcome}".lower()

    if any(kw in text for kw in ("football", "nfl", "super bowl", "basketball", "nba", "soccer", "fifa", "baseball", "mlb", "hockey", "nhl")):
        return """COLOR PALETTE: Rich stadium greens (#2d6a4f), warm floodlight amber (#ffb703), deep shadow blacks (#1a1a2e), jersey-saturated primaries. Scoreboard neon glow bleeding into the mist of a packed arena.
TEXTURES: Sweat-sheened skin catching stadium light, grass blades bending under cleats, scuffed leather on the ball, worn grip tape on helmets, the matte sheen of polyester jerseys under broadcast lighting. Crowd is a vibrating bokeh of colors and motion in the deep background.
ATMOSPHERE: Humid stadium air with visible breath in cold games, confetti particles catching light, dust kicked up from turf, the electric tension of 70,000 people holding their breath."""

    if any(kw in text for kw in ("mars", "moon", "space", "rocket", "astronaut", "nasa", "spacex", "orbit", "colonize", "launch")):
        return """COLOR PALETTE: Deep void black (#0a0a0a), nebula purples (#5e2ca5), Mars oxide red (#c1440e), ice-blue engine glow (#7ec8e3), golden sun-on-visor reflections. Stark contrast between sunlit surfaces and absolute shadow.
TEXTURES: Brushed titanium hull panels, dusty regolith coating boots and wheels, frosted glass visors with interior HUD reflections, crinkled thermal blankets in gold foil, the grainy surface of alien terrain stretching to a curved horizon.
ATMOSPHERE: Perfect silence implied through slow particle drift, micro-debris floating in zero-g, exhaust plumes expanding into vacuum, the loneliness of vast emptiness punctuated by a single human figure."""

    if any(kw in text for kw in ("bitcoin", "crypto", "ethereum", "stock", "nasdaq", "market", "recession", "inflation", "fed")):
        return """COLOR PALETTE: Bloomberg terminal green (#00d26a), panic-sell red (#ff3b30), dark trading floor navy (#0d1b2a), screen-glow cyan (#00f0ff), gold (#ffd700) for wealth imagery. Screens cast colored light onto stressed faces.
TEXTURES: Glossy glass desktops reflecting ticker data, loosened silk ties, rolled-up dress shirt sleeves, the matte plastic of dozens of keyboards, coffee-stained papers scattered across desks, smooth LCD pixel grids visible up close.
ATMOSPHERE: Fluorescent overhead mixed with screen-glow creating an anxious, sleepless energy. Papers flutter from a slammed fist. The air feels electrically charged with billions on the line."""

    if any(kw in text for kw in ("election", "president", "vote", "congress", "political", "campaign")):
        return """COLOR PALETTE: Patriotic deep blue (#002868), bold red (#BF0A30), pure white (#FFFFFF), warm stage-light gold (#e8a317), confetti rainbow bursts. Night sky behind stage rigging.
TEXTURES: Crisp suit fabrics under harsh stage lights, waving fabric flags with visible thread patterns, glossy podium surfaces reflecting teleprompter glow, printed campaign signs with slightly curled edges, confetti mid-air catching spotlights.
ATMOSPHERE: The electric anticipation of a historic announcement — camera flashes strobing, crowd roar implied through open mouths and raised fists, a single figure at a podium bathed in warm light against a sea of supporters."""

    if any(kw in text for kw in ("hurricane", "tornado", "earthquake", "flood", "wildfire", "climate", "weather")):
        return """COLOR PALETTE: Storm-dark charcoal (#2b2d42), lightning white (#f8f9fa), flood-water murky brown (#8d6e63), fire orange (#ff6d00), emergency red (#d00000). Nature's palette at its most extreme.
TEXTURES: Rain-slicked surfaces reflecting emergency lights, splintered wood and bent metal, churning muddy water with debris, wind-whipped fabric and hair, cracked dry earth, ash-covered surfaces, ice crystals forming on windshields.
ATMOSPHERE: The overwhelming sensory assault of nature's fury — horizontal rain, flying debris, the ground itself shaking, walls of water or fire approaching. Scale communicated through tiny human figures against enormous natural forces."""

    if any(kw in text for kw in ("ai", "artificial intelligence", "robot", "tech", "tesla", "quantum")):
        return """COLOR PALETTE: Clean white (#fafafa), accent electric blue (#0066ff), subtle neon cyan (#00e5ff), dark carbon (#1a1a1a), holographic iridescence. Minimal, Apple-keynote-clean aesthetic with occasional warm amber accents.
TEXTURES: Brushed aluminum surfaces, tempered glass with fingerprint smudges, soft-touch matte plastics, fiber optic strands pulsing with light, pristine white lab coats, the subtle hum-glow of server rack LEDs reflected in polished floors.
ATMOSPHERE: The hushed reverence of a breakthrough moment — clean air, soft ambient hum, a single screen illuminating a face in blue-white light. The boundary between human and machine feels paper-thin."""

    return """COLOR PALETTE: Cinematic teal (#008080) and orange (#ff8c00) complementary grade, deep blacks (#0a0a0a) for contrast, selective warm highlights on key subjects. Film-grain warmth.
TEXTURES: Real-world material authenticity — fabric weaves, metal scratches, wood grain, skin pores, dust motes in shafts of light. Nothing looks plastic or CG-smooth.
ATMOSPHERE: The charged air of a pivotal moment — the second before everything changes. Dramatic natural or practical lighting, no flat even illumination. Depth through atmospheric haze, volumetric light, and shallow focus on the decisive element."""


def _domain_animation(title: str, outcome: str) -> str:
    text = f"{title} {outcome}".lower()

    if any(kw in text for kw in ("football", "nfl", "super bowl", "basketball", "nba", "soccer", "fifa", "baseball", "mlb", "hockey", "nhl")):
        return """CAMERA: Start with a dramatic low-angle hero shot (0-2s), rack focus to the decisive play unfolding (2-5s), then sweep into a wide celebratory crane shot pulling back to reveal the roaring crowd (5-8s). Handheld micro-shake for broadcast authenticity.
ANIMATION: Peak athletic motion — muscles tensing, sweat droplets flying in slow-motion, ball spinning with visible rotation, crowd doing the wave in sync. Speed ramps: slow-mo on the critical moment (catch/dunk/goal), then real-time explosion of celebration.
IMPLIED SOUND: The thunderous roar of a stadium erupting, the sharp crack of contact, sneakers squeaking on hardwood, the whoosh of a ball cutting through air."""

    if any(kw in text for kw in ("mars", "moon", "space", "rocket", "astronaut", "nasa", "spacex", "orbit", "colonize", "launch")):
        return """CAMERA: Slow, reverent dolly across the spacecraft/surface (0-3s), then a breathtaking wide pull-back revealing the enormity of space/planet (3-6s), ending on a close-up of a visor reflection showing what they've achieved (6-8s). Smooth, weightless camera movement.
ANIMATION: Zero-gravity float of particles and tools, slow thrust plume expansion, gentle rotation of spacecraft catching sunlight, dust settling in low gravity with impossibly slow arcs. Boot prints forming in regolith. Stars twinkling through thin atmosphere.
IMPLIED SOUND: Deep, resonant silence punctuated by radio crackle, the rumble of distant engines through hull vibration, the hiss of an airlock, a heartbeat."""

    if any(kw in text for kw in ("bitcoin", "crypto", "stock", "nasdaq", "market", "recession", "inflation", "fed")):
        return """CAMERA: Tight on screens with rapid chart movement (0-2s), whip-pan to human reactions — faces lit by green/red screens (2-5s), then pull back to reveal the entire trading floor in chaos or celebration (5-8s). Slight Dutch angle for tension.
ANIMATION: Charts animating in real-time with smooth line draws, ticker numbers rolling, phone screens lighting up simultaneously, papers being thrown in the air, a coffee cup vibrating from a slammed desk. Multiple screens reflecting in glasses.
IMPLIED SOUND: The cacophony of a trading floor — shouting, ringing phones, keyboards clacking frantically, the ding of price alerts firing off."""

    if any(kw in text for kw in ("election", "president", "vote", "congress", "political", "campaign")):
        return """CAMERA: Slow push-in on the podium/stage through the crowd (0-3s), dramatic reveal of the decisive moment — vote count, victory declaration (3-6s), pull back to aerial showing the scale of the crowd reaction (6-8s). Steadicam through the crowd.
ANIMATION: Confetti cannons firing in slow motion, flags rippling in wind, crowd hands rising in a wave, camera flashes creating a strobe effect, balloons dropping from ceiling netting. The decisive number ticking over on a giant screen.
IMPLIED SOUND: Building crowd roar reaching crescendo, the echo of a voice through a PA system, thunderous applause, fireworks."""

    if any(kw in text for kw in ("hurricane", "tornado", "earthquake", "flood", "wildfire", "climate", "weather")):
        return """CAMERA: Ground-level establishing shot showing the approaching force (0-2s), dramatic tracking shot following the impact zone (2-5s), pulling up to aerial revealing the full scale of devastation or power (5-8s). Camera shake from environmental forces.
ANIMATION: Trees bending to breaking point, water surging and swirling with debris, lightning crackling across the sky in branching patterns, fire consuming structures with realistic spread, ground cracking and shifting. Rain drops visible as individual streaks in slow-mo.
IMPLIED SOUND: The freight-train roar of a tornado, the deep rumble of an earthquake, the relentless howl of hurricane winds, the crackling inferno of wildfire."""

    if any(kw in text for kw in ("ai", "artificial intelligence", "robot", "tech", "tesla", "quantum")):
        return """CAMERA: Ultra-smooth dolly across the technology (0-2s), rack focus from the tech to the human face reacting (2-5s), then a dramatic wide revealing the full scale of the breakthrough (5-8s). Precise, almost robotic camera movement.
ANIMATION: Data flowing through fiber optics as light pulses, holographic interfaces materializing, robotic joints articulating with precision, neural network visualizations pulsing, a screen transitioning from code to result. Subtle lens flare from LEDs.
IMPLIED SOUND: A soft electronic hum building to a crescendo, the click of a final keystroke, a synthesized tone of completion, the whir of cooling fans."""

    return """CAMERA: Establishing wide shot with slow push-in (0-2s), dynamic mid-shot capturing the decisive action (2-5s), emotional close-up or dramatic wide pullback for the payoff (5-8s). Cinematic depth of field throughout.
ANIMATION: Natural, physics-grounded motion with weight and momentum. Speed ramps for emphasis on the critical moment. Environmental details in motion — wind, particles, fabric, hair. Subtle parallax between foreground and background layers.
IMPLIED SOUND: The specific ambient soundscape of the environment building to the climactic moment — then a beat of near-silence before the payoff."""


def create_video_prompt(
    title: str,
    outcome: str,
    original_trade_link: str
) -> str:
    domain_rules = _domain_specific_rules(title=title, outcome=outcome)
    palette = _domain_palette(title=title, outcome=outcome)
    animation = _domain_animation(title=title, outcome=outcome)

    return f"""Create an 8-second vertical cinematic video from the provided start frame.

TOPIC: {title}
SCENARIO TO DEPICT: {outcome}

NARRATIVE ARC:
Show the described scenario unfolding as a single continuous, dramatic moment. The viewer should feel like they're watching the most pivotal 8 seconds of a blockbuster film about this exact event. Every frame must serve the story — no filler, no static holds, no dead time.

VISUAL IDENTITY:
{palette}

ANIMATION & CAMERA DIRECTION:
{animation}

CONTINUITY & PHYSICS (HIGHEST PRIORITY):
- Follow real-world physics: momentum, gravity, contact, and inertia must be believable.
- No impossible motion: no teleporting, time jumps, reverse playback, or sudden scene mutations.
- Preserve identity and count consistency for all key subjects from first frame to final frame.
- Actions must remain causal and logical; each frame should follow naturally from the previous frame.
- Keep continuity with the source image used as the starting frame — same characters, same environment, same lighting direction.
{domain_rules}

BRANDED ATMOSPHERE (subtle, environmental — never the main focus):
- Maintain any branded elements from the start frame: green line graphs on screens, "K" logos on banners, percentage numbers on scoreboards, green (#00d26a) LED accents.
- These elements should animate naturally (graphs tick upward, banners sway, LEDs pulse) — never freeze or pop in/out.
- Prefer graphical elements (charts, arrows, logos) over words. Any visible text MUST be in English only — keep it to short numbers or single words.
- They must stay background dressing, never compete with the main action.

QUALITY TARGET:
- Premium photorealistic cinematic quality — this should look like it belongs on Netflix, not a student film.
- Rich, detailed textures on every surface: skin pores, fabric weaves, metal reflections, environmental particles.
- Dramatic lighting with depth — volumetric rays, rim lighting on key subjects, motivated shadows. No flat, even illumination.
- Natural motion blur on fast movement, film-grain texture for organic feel, shallow depth of field to guide the eye.
- Dynamic camera motion with clean composition and intentional framing.

OUTPUT RULES:
- Vertical 9:16 composition optimized for mobile viewing.
- No floating UI overlays, no literal app screenshots, no plain-text watermarks.
- No identity drift, no face morphing, no unrelated extra subjects appearing mid-clip.
- No static slideshow look — every frame must have visible motion and life."""
