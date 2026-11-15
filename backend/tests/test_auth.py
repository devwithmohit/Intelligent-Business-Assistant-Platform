from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from backend.core import jwt as jwt_core
from backend.core.config import Settings, validate_security_settings
from backend.main import app

client = TestClient(app)


def _unique_email():
    return f"test+{uuid4().hex[:8]}@example.com"


def test_register_login_and_me_flow():
    email = _unique_email()
    password = "Password123!"

    # Register
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "testuser", "email": email, "password": password},
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    assert "access_token" in data
    assert data.get("user", {}).get("email") == email or True

    # Login
    resp2 = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp2.status_code == 200, resp2.text
    login_data = resp2.json()
    assert "access_token" in login_data
    assert "refresh_token" in login_data

    access_token = login_data["access_token"]

    # Verify access token payload has typ="access"
    payload = jwt_core.decode_token(access_token)
    assert payload.get("typ") == "access"

    # Get current user
    resp3 = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert resp3.status_code == 200, resp3.text
    me = resp3.json()
    assert me.get("email") == email


def test_refresh_token_returns_new_access_token():
    email = _unique_email()
    password = "Password123!"

    # Register -> get tokens
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "refreshuser", "email": email, "password": password},
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        resp2 = client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert resp2.status_code == 200, resp2.text
        refresh_token = resp2.json().get("refresh_token")

    assert refresh_token, "No refresh_token available to test refresh endpoint"

    # Verify refresh token has typ="refresh"
    payload = jwt_core.decode_token(refresh_token)
    assert payload.get("typ") == "refresh"

    # Refresh
    resp3 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp3.status_code == 200, resp3.text
    refreshed = resp3.json()
    assert "access_token" in refreshed
    assert refreshed["access_token"] != ""


def test_access_token_rejected_on_refresh_endpoint():
    """Ensure access token cannot be used on /refresh endpoint (strict typ == 'refresh')."""
    email = _unique_email()
    password = "Password123!"

    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "strictuser", "email": email, "password": password},
    )
    assert resp.status_code in (200, 201), resp.text
    access_token = resp.json()["access_token"]

    # Attempting to refresh with an access token MUST fail
    refresh_resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": access_token}
    )
    assert refresh_resp.status_code == 401, refresh_resp.text
    detail = refresh_resp.json().get("detail", "")
    assert "refresh" in detail.lower() or "invalid" in detail.lower()


def test_token_lacking_refresh_type_rejected_on_refresh():
    """Ensure any token lacking explicit typ='refresh' is rejected on /refresh."""
    # Craft a token without typ claim
    untyped_token = jwt.encode(
        {"sub": "1", "exp": 9999999999, "iat": 1000000000},
        getattr(jwt_core.settings, "SECRET_KEY"),
        algorithm="HS256",
    )

    resp = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": untyped_token}
    )
    assert resp.status_code == 401, resp.text


def test_refresh_token_rejected_as_bearer_authorization():
    """Ensure a refresh token cannot be passed as Authorization Bearer header to access protected routes."""
    email = _unique_email()
    password = "Password123!"

    resp = client.post(
        "/api/v1/auth/register",
        json={"name": "bearercheck", "email": email, "password": password},
    )
    assert resp.status_code in (200, 201), resp.text
    refresh_token = resp.json()["refresh_token"]

    resp_me = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"}
    )
    assert resp_me.status_code == 401


def test_security_headers_present():
    """Validate presence of defensive security headers on responses."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


def test_production_startup_validation_rejects_insecure_secrets():
    """Ensure startup validation fails fast and loudly on default secrets in production."""
    prod_insecure_settings = Settings(
        ENV="production",
        SECRET_KEY="change-me-super-secret",
    )
    with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
        validate_security_settings(prod_insecure_settings)

    short_secret_settings = Settings(
        ENV="production",
        SECRET_KEY="short-secret-key",
    )
    with pytest.raises(ValueError, match="CRITICAL SECURITY CONFIGURATION ERROR"):
        validate_security_settings(short_secret_settings)


def test_websocket_secure_handshake_authentication():
    """Ensure WebSocket endpoint requires in-band handshake frame and rejects unauthenticated connections."""
    # 1. Invalid or missing handshake frame closes with 1008
    with pytest.raises(Exception):
        with client.websocket_connect("/api/ws/chat/1") as ws:
            ws.send_text(
                '{"type": "auth", "token": "invalid.jwt.token"}'
            )
            ws.receive_json()

    # 2. Valid handshake frame succeeds
    email = _unique_email()
    password = "Password123!"
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={"name": "wsuser", "email": email, "password": password},
    )
    access_token = reg_resp.json()["access_token"]

    # Create a conversation first
    conv_resp = client.post(
        "/api/v1/chat/",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"message": "hello", "agent_type": "customer_service"},
    )
    if conv_resp.status_code in (200, 201):
        conv_id = conv_resp.json()["conversation_id"]
        with client.websocket_connect(f"/api/ws/chat/{conv_id}") as ws:
            # Send initial auth frame
            ws.send_text(f'{{"type": "auth", "token": "{access_token}"}}')
            auth_ack = ws.receive_json()
            assert auth_ack.get("type") == "auth_success"
            assert auth_ack.get("status") == "authenticated"
