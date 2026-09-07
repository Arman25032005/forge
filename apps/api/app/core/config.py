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
    refresh_token_days: int = 7

    # "memory" (default, this environment) or "redis" (multi-instance
    # deployments — not exercised here, no live Redis; see rate_limit.py).
    rate_limit_backend: str = "memory"
    login_rate_limit_max: int = 5
    login_rate_limit_window_seconds: int = 60
    register_rate_limit_max: int = 5
    register_rate_limit_window_seconds: int = 60

    # Unset in this development environment — the agent runtime's real
    # reasoning provider (AnthropicProvider) is implemented but cannot be
    # exercised end-to-end without one. See docs/architecture/phase-5-agent-runtime.md.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5"
    agent_max_steps: int = 8


@lru_cache
def get_settings() -> Settings:
    return Settings()
