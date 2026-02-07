def create_video_prompt(
    title: str,
    caption: str,
    original_bet_link: str,
) -> str:
    """
    Build a Veo prompt that animates forward from the first frame.
    """
    return f"""Animate this image into an exciting 8-second action clip.

ACTION: {caption}

RULES:
- Continue the motion naturally from this starting frame
- Physically realistic movement
- Forward motion, building energy
- Professional sports broadcast style
- Cinematic, dynamic camera work

Make it exciting and action-packed."""
