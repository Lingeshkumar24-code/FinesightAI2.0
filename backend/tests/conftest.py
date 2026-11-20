import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./finsight-test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    resp = client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "anything"}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
