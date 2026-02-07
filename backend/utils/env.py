from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    GOOGLE_CLOUD_PROJECT: str
    GOOGLE_CLOUD_LOCATION: str
    GOOGLE_CLOUD_BUCKET_NAME: str
    GOOGLE_APPLICATION_CREDENTIALS: str | None = None
    CLOUD_TASKS_QUEUE: str
    CLOUD_TASKS_LOCATION: str
    WORKER_SERVICE_URL: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )
settings = Settings()