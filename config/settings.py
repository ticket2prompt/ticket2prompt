"""Application configuration from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    postgres_url: str = ""
    redis_url: str = "redis://localhost:6379"
    qdrant_url: str = "http://localhost:6333"
    embedding_model: str = "bge-small-en"
    embedding_dim: int = 384
    api_port: int = 8000
    log_level: str = "INFO"
    debug: bool = False

    # GitHub integration (non-credential settings)
    github_api_url: str = "https://api.github.com"

    # Webhooks
    github_webhook_secret: str = ""

    # Auth
    jwt_secret: str = ""
    jwt_expiry_hours: int = 24
    credential_encryption_key: str = ""

    # Repository cloning
    clone_base_dir: str = "/tmp/ticket-to-prompt-repos"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    """Return a Settings instance."""
    return Settings()
