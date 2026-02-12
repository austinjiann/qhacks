from pydantic_settings import BaseSettings, SettingsConfigDict

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
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )
    
settings = Settings()