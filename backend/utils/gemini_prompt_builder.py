def create_first_image_prompt(
    title: str,
    outcome: str,
    original_bet_link: str,
    style: str = "action",
) -> str:
    """
    Build the first-frame prompt for Gemini.
    style: "action" (realistic) or "animated" (2D stylized)
    """

    # Logic constraints to prevent AI nonsense
    logic_rules = """
LOGIC RULES (CRITICAL - DO NOT VIOLATE):
- If this involves a real person (athlete, politician, celebrity), they must look like themselves
- If this is a sport, follow that sport's actual rules and equipment:
  - Football: Players wear helmets at all times during play, proper pads, correct team uniforms
  - Basketball: No helmets, proper jerseys, indoor court
  - Soccer: Shin guards, cleats, outdoor pitch
- Equipment does not disappear or change mid-scene
- Physics must be realistic (no floating, no impossible body positions)
- Team colors and logos must be accurate to the real teams
- If showing a specific person, their face must match real photos of them
"""

    if style == "animated":
        return f"""Create a stylized 2D animated frame (9:16 vertical).

SCENARIO: {title}
OUTCOME TO SHOW: {outcome}

STYLE:
- Beautiful 2D animation like anime or Pixar concept art
- Bold colors, clean lines, stylized but recognizable
- Dramatic composition with depth
- Can be fantastical but characters must still be recognizable

{logic_rules}

NO text, watermarks, or UI elements.
Create one stunning animated frame."""

    # Default: action/realistic
    return f"""Create a photorealistic 4K action frame (9:16 vertical).

SCENARIO: {title}
OUTCOME TO SHOW: {outcome}

STYLE:
- ESPN/broadcast quality sports photography
- Peak action moment with motion and energy
- Accurate uniforms, equipment, and setting
- Dramatic lighting, stadium atmosphere

{logic_rules}

NO text, watermarks, or UI elements.
Create one powerful action frame."""
