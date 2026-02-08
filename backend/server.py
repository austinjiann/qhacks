import os
from utils.env import settings

# Export credentials to os.environ so Google Cloud clients (GCS, Vertex AI) can find them
if settings.GOOGLE_APPLICATION_CREDENTIALS:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS

from blacksheep import Application
from rodi import Container

from services.test_service import TestService
from services.feed_service import FeedService
from services.job_service import JobService
from services.vertex_service import VertexService
from services.youtube_service import YoutubeService
from services.kalshi_service import KalshiService

services = Container()
services.add_scoped(TestService)
services.add_scoped(YoutubeService)
services.add_scoped(KalshiService)
services.add_scoped(FeedService)
services.add_singleton(VertexService)
services.add_singleton(JobService)

app = Application(services=services)

app.use_cors(
    allow_methods="*",
    allow_origins="*",
    allow_headers="*",
)
