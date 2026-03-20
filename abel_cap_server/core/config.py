from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="CAP_",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "abel-cap"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    log_json: bool = False
    cap_upstream_base_url: str = Field(
        default="https://gateway.abel.ai/api",
        validation_alias=AliasChoices("CAP_UPSTREAM_BASE_URL", "CAP_CAP_UPSTREAM_BASE_URL"),
    )
    cap_upstream_timeout_seconds: float = 10.0
    cap_provider_name: str = "Abel AI"
    cap_provider_url: str = "https://abel.ai"
    gateway_api_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
