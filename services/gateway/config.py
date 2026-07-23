from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    AUTH_SERVICE_URL: str = "http://localhost:8001"
    DOCUMENT_SERVICE_URL: str = "http://localhost:8002"
    CHAT_SERVICE_URL: str = "http://localhost:8003"
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
