def _base_style_prompt() -> str:
    return (
        "Cinematic vertical short frame, realistic lighting, crisp detail, "
        "dynamic sports/news atmosphere, no text overlays, no subtitles."
    )


def create_first_image_prompt(
    title: str,
    caption: str,
    original_bet_link: str,
) -> str:
    """
    Build a first-frame prompt for Gemini image generation.
    """
    return "\n".join(
        [
            _base_style_prompt(),
            f"Title context: {title}",
            f"Scene context: {caption}",
            f"Bet context link: {original_bet_link}",
            "Generate the opening keyframe of the story.",
        ]
    )


