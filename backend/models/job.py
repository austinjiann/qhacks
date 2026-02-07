from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal

@dataclass
class VideoJobRequest:
    """Request to create a video job"""
    title: str
    outcome: str
    original_bet_link: str
    duration_seconds: int = 8
    shorts_style: str = "action"  # "action" or "animated"
    source_image_url: Optional[str] = None  # Optional image to use as base
    character_image_urls: list[str] = field(default_factory=list)  # Character headshot URLs
    
@dataclass
class JobStatus:
    status: Optional[Literal["done", "waiting", "error"]]
    job_start_time: Optional[datetime] = None
    job_end_time: Optional[datetime] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    original_bet_link: Optional[str] = None
    image_url: Optional[str] = None
