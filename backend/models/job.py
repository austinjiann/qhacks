from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Literal

@dataclass
class VideoJobRequest:
    title: str
    outcome: str
    original_trade_link: str
    source_image_url: Optional[str] = None
    kalshi: Optional[list] = None
    trade_side: Optional[str] = None

@dataclass
class JobStatus:
    status: Optional[Literal["done", "waiting", "error"]]
    job_start_time: Optional[datetime] = None
    job_end_time: Optional[datetime] = None
    video_url: Optional[str] = None
    error: Optional[str] = None
    original_trade_link: Optional[str] = None
    image_url: Optional[str] = None
