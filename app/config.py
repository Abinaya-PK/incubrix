from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@postgres:5432/app"
    redis_url: str = "redis://redis:6379/0"
    s3_endpoint: str = "http://minio:8333"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "broll"

    pexels_api_key: str = ""
    pixabay_api_key: str = ""

    footage_provider: str = "mock"
    asr_provider: str = "mock"
    tts_provider: str = "mock"
    llm_provider: str = "mock"

    min_scene_seconds: float = 2.5
    max_scene_seconds: float = 8.0
    max_audio_minutes: int = 10


settings = Settings()
