from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from abel_cap_server.core.config import Settings
from abel_cap_server.main import create_app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app = create_app(Settings(app_env="test", log_json=False))
    with TestClient(app) as test_client:
        yield test_client
