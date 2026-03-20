import pytest
from pydantic import ValidationError

from abel_cap_server.core.config import Settings


def test_settings_requires_cap_upstream_base_url(monkeypatch) -> None:
    monkeypatch.delenv("CAP_UPSTREAM_BASE_URL", raising=False)
    monkeypatch.delenv("CAP_CAP_UPSTREAM_BASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_accepts_cap_upstream_base_url_env_var(monkeypatch) -> None:
    monkeypatch.setenv("CAP_UPSTREAM_BASE_URL", "https://example.invalid/api")

    settings = Settings(_env_file=None)

    assert settings.cap_upstream_base_url == "https://example.invalid/api"


def test_settings_do_not_ship_default_gateway_api_key(monkeypatch) -> None:
    monkeypatch.delenv("CAP_GATEWAY_API_KEY", raising=False)

    settings = Settings(_env_file=None, cap_upstream_base_url="https://example.invalid/api")

    assert settings.gateway_api_key is None
