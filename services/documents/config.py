from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./documents.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    UPLOAD_DIR: str = "./uploads"
    FAISS_DIR: str = "./faiss_indexes"

    class Config:
        env_file = ".env"


settings = Settings()
