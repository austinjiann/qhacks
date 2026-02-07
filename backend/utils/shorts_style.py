from typing import Literal

Style = Literal["action", "animated"]
DEFAULT_STYLE: Style = "action"

_STYLE_ALIASES: dict[str, Style] = {
    # Action/realistic
    "action": "action",
    "action_commentary": "action",
    "realistic": "action",
    "sports": "action",

    # Animated/stylized
    "animated": "animated",
    "animation": "animated",
    "2d": "animated",
    "fantasy": "animated",
    "fantasy_ai_gen": "animated",
    "vibe_music_edit": "animated",
    "stylized": "animated",
}


def normalize_style(style: str | None) -> Style:
    """Normalize style input to 'action' or 'animated'."""
    normalized = (style or "").strip().lower()
    return _STYLE_ALIASES.get(normalized, DEFAULT_STYLE)


# Keep old name for backward compatibility
def normalize_shorts_style(style: str | None) -> Style:
    return normalize_style(style)
