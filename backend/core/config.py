"""Application configuration via Pydantic settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SAVERY_",
        extra="ignore",
    )

    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = True

    project_name: str = "Savery API"
    version: str = "0.1.0"

    api_prefix: str = "/api"
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    openapi_url: str = "/openapi.json"

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/savery"

    celery_broker_url: str = "amqp://guest:guest@localhost//"
    celery_result_backend: str = "redis://localhost:6379/0"
    celery_route_task: str = "workers.optimize.plan_route"

    task_status_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached copy of settings so they are only computed once."""

    return Settings()


settings = get_settings()
