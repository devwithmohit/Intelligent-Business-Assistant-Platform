from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.core import database
from backend.main import app


database.init_db(create_tables=True)


def _unique_email() -> str:
    return f"codex+{uuid4().hex[:10]}@example.com"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(client):
    email = _unique_email()
    password = "Password123!"
    register_response = client.post(
        "/api/v1/auth/register",
        json={"name": "Test User", "email": email, "password": password},
    )
    assert register_response.status_code in (200, 201), register_response.text

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
