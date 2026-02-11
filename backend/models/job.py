from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal

@dataclass
class VideoJobRequest:
    """Request to create a video job"""
    title: str
    outcome: str
    original_trade_link: str
    source_image_url: Optional[str] = None  # Optional real image to use as base
    kalshi: Optional[list] = None  # Market data to attach to generated video
    trade_side: Optional[str] = None  # YES or NO

@dataclass
class JobStatus:
    status: Optional[Literal["done", "waiting", "error"]]
    job_start_time: Optional[datetime] = None
    job_end_time: Optional[datetime] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    original_trade_link: Optional[str] = None
    image_url: Optional[str] = None
