from collections.abc import Generator
import os

import pytest
from fastapi.testclient import TestClient

from abel_cap_server.core.config import Settings

os.environ.setdefault("CAP_UPSTREAM_BASE_URL", "https://example.invalid/api")

from abel_cap_server.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app(
        Settings(
            app_env="test",
            log_json=False,
            cap_upstream_base_url="https://example.invalid/api",
        )
    )
    with TestClient(app) as test_client:
        yield test_client
