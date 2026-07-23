from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./chat.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    DOCUMENT_SERVICE_URL: str = "http://localhost:8002"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:0.5b"
    OLLAMA_TIMEOUT: int = 180
    OLLAMA_NUM_CTX: int = 8192
    OLLAMA_NUM_PREDICT: int = 220

    class Config:
        env_file = ".env"


settings = Settings()
