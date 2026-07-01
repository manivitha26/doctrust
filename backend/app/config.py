from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Application metadata
    APP_NAME: str = "DocuTrust API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Security
    JWT_SECRET_KEY: str = "change-me-to-a-strong-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "docutrust_db"
    MONGODB_COLLECTION: str = "documents"

    # LLM (optional)
    OPENAI_API_KEY: Optional[str] = None
    USE_OLLAMA: bool = False
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"

    # Rate limiting strings (compatible with slowapi)
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_QUERY: str = "20/minute"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
