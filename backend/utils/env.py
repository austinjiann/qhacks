from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import os
import base64

class Settings(BaseSettings):
    KALSHI_API_KEY: str
    KALSHI_PRIVATE_KEY_PATH: str = "./kalshi_private_key.pem"
    KALSHI_PRIVATE_KEY_BASE64: str | None = None
    OPENAI_API_KEY: str
    YOUTUBE_API_KEY: str
    GOOGLE_CLOUD_PROJECT: str = ""
    GOOGLE_CLOUD_LOCATION: str = "us-central1"
    GOOGLE_CLOUD_BUCKET_NAME: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None
    CLOUD_TASKS_QUEUE: str = ""
    CLOUD_TASKS_LOCATION: str = "us-central1"
    WORKER_SERVICE_URL: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"
    VERTEX_AI_API_KEY: str = ""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )
    
    def get_kalshi_private_key(self) -> str:
        """Get Kalshi private key from either base64 env var or file"""
        if self.KALSHI_PRIVATE_KEY_BASE64:
            return base64.b64decode(self.KALSHI_PRIVATE_KEY_BASE64).decode('utf-8')
        else:
            with open(self.KALSHI_PRIVATE_KEY_PATH, 'r') as f:
                return f.read()

settings = Settings()