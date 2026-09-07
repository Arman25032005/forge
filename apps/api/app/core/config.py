from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FORGE_", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://forge:forge@localhost:5432/forge"
    redis_url: str = "redis://localhost:6379/0"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    jwt_secret: str = "dev-only-secret-change-me-please-32bytes-min"
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
