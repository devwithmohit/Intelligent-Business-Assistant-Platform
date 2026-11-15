from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.core.database import SessionLocal, init_db
from backend.core.encryption import (
    decrypt_integration_config,
    decrypt_payload,
    encrypt_integration_config,
    encrypt_payload,
    redact_sensitive_values,
)
from backend.main import app
from backend.models.integration_models import Integration

client = TestClient(app)


def _register_user(name: str) -> tuple[dict[str, str], int]:
    email = f"{name}_{uuid4().hex[:6]}@example.com"
    password = "Password123!"
    resp = client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password},
    )
    assert resp.status_code in (200, 201), resp.text
    token = resp.json()["access_token"]
    user_id = resp.json().get("user", {}).get("id", 1)
    return {"Authorization": f"Bearer {token}"}, user_id


def test_credential_encryption_and_decryption():
    """Ensure integration payloads are symmetrically encrypted with Fernet and decrypted properly."""
    raw_secrets = {
        "api_key": "xoxb-12345-secret-key",
        "client_secret": "super-confidential-secret",
        "webhook_url": "https://hooks.slack.com/services/XYZ",
    }

    # 1. Direct encryption
    token = encrypt_payload(raw_secrets)
    assert isinstance(token, str)
    assert "xoxb-12345" not in token

    decrypted = decrypt_payload(token)
    assert decrypted == raw_secrets

    # 2. Integration config envelope
    envelope = encrypt_integration_config(raw_secrets)
    assert envelope["_encrypted"] is True
    assert "ciphertext" in envelope
    assert "xoxb-12345" not in str(envelope)

    unwrapped = decrypt_integration_config(envelope)
    assert unwrapped == raw_secrets


def test_redact_sensitive_values():
    """Ensure sensitive keys are masked before sending via API."""
    payload = {
        "name": "gmail_integration",
        "type": "gmail",
        "api_key": "secret-api-key-123",
        "password": "mypassword",
        "client_secret": "confidential",
        "nested": {
            "token": "token-value",
            "public_id": "public-123",
        },
        "port": 587,
    }
    redacted = redact_sensitive_values(payload)
    assert redacted["name"] == "gmail_integration"
    assert redacted["api_key"] == "********"
    assert redacted["password"] == "********"
    assert redacted["client_secret"] == "********"
    assert redacted["nested"]["token"] == "********"
    assert redacted["nested"]["public_id"] == "public-123"
    assert redacted["port"] == 587


def test_cross_tenant_integration_isolation():
    """Ensure User B cannot view, edit, or delete User A's integration configs."""
    headers_user_a, _ = _register_user("user_a")
    headers_user_b, _ = _register_user("user_b")

    # User A creates an integration with sensitive secrets
    integ_name = f"slack_{uuid4().hex[:6]}"
    create_payload = {
        "name": integ_name,
        "type": "slack",
        "api_key": "xoxb-tenant-a-secret",
        "channel": "#general",
    }
    resp_create = client.post(
        "/api/v1/integrations/", json=create_payload, headers=headers_user_a
    )
    assert resp_create.status_code == 201
    body_a = resp_create.json()
    assert body_a["config"]["api_key"] == "********"  # Secret redirected/redacted

    # Verify that raw database row contains ciphertext, NOT plaintext
    db = SessionLocal()
    try:
        row = db.query(Integration).filter(Integration.name == integ_name).first()
        assert row is not None
        assert row.config.get("_encrypted") is True
        assert "xoxb-tenant-a-secret" not in str(row.config)
    finally:
        db.close()

    # User B lists integrations: must NOT see User A's integration
    resp_b_list = client.get("/api/v1/integrations/", headers=headers_user_b)
    assert resp_b_list.status_code == 200
    assert integ_name not in resp_b_list.json()

    # User B attempts to access User A's integration directly -> 404 Not Found
    resp_b_get = client.get(
        f"/api/v1/integrations/{integ_name}", headers=headers_user_b
    )
    assert resp_b_get.status_code == 404

    # User B attempts to update User A's integration -> 404 Not Found
    resp_b_put = client.put(
        f"/api/v1/integrations/{integ_name}",
        json={"name": integ_name, "type": "slack", "api_key": "hacked"},
        headers=headers_user_b,
    )
    assert resp_b_put.status_code == 404

    # User B attempts to delete User A's integration -> 404 Not Found
    resp_b_del = client.delete(
        f"/api/v1/integrations/{integ_name}", headers=headers_user_b
    )
    assert resp_b_del.status_code == 404

    # User A can still retrieve and delete their own integration
    resp_a_get = client.get(
        f"/api/v1/integrations/{integ_name}", headers=headers_user_a
    )
    assert resp_a_get.status_code == 200
    assert resp_a_get.json()["api_key"] == "********"

    resp_a_del = client.delete(
        f"/api/v1/integrations/{integ_name}", headers=headers_user_a
    )
    assert resp_a_del.status_code == 200


def test_cross_tenant_workflow_isolation():
    """Ensure User B cannot view, execute, or delete User A's workflows."""
    headers_user_a, _ = _register_user("wf_user_a")
    headers_user_b, _ = _register_user("wf_user_b")

    wf_name = f"flow_{uuid4().hex[:6]}"
    workflow_payload = {
        "name": wf_name,
        "description": "Tenant A workflow",
        "nodes": [
            {"id": "start", "agent": "customer_service", "config": {}},
            {"id": "end", "agent": "customer_service", "config": {}},
        ],
        "edges": [{"src": "start", "dst": "end"}],
    }

    # User A creates workflow
    resp_create = client.post(
        "/api/v1/workflows/", json=workflow_payload, headers=headers_user_a
    )
    assert resp_create.status_code == 201

    # User B lists workflows -> User A's workflow is not visible
    resp_b_list = client.get("/api/v1/workflows/", headers=headers_user_b)
    assert resp_b_list.status_code == 200
    wf_names_b = [w["name"] for w in resp_b_list.json()]
    assert wf_name not in wf_names_b

    # User B tries to get User A's workflow -> 404
    resp_b_get = client.get(
        f"/api/v1/workflows/{wf_name}", headers=headers_user_b
    )
    assert resp_b_get.status_code == 404

    # User B tries to delete User A's workflow -> 404
    resp_b_del = client.delete(
        f"/api/v1/workflows/{wf_name}", headers=headers_user_b
    )
    assert resp_b_del.status_code == 404

    # User B tries to start User A's workflow -> 404
    resp_b_start = client.post(
        f"/api/v1/workflows/{wf_name}/start",
        json={"workflow_name": wf_name, "start_node": "start"},
        headers=headers_user_b,
    )
    assert resp_b_start.status_code == 404

    # User A can access and delete their workflow
    resp_a_get = client.get(
        f"/api/v1/workflows/{wf_name}", headers=headers_user_a
    )
    assert resp_a_get.status_code == 200

    resp_a_del = client.delete(
        f"/api/v1/workflows/{wf_name}", headers=headers_user_a
    )
    assert resp_a_del.status_code == 204


def test_analytics_tenancy_isolation():
    """Ensure analytics endpoints filter data strictly by tenant user context."""
    headers_user_a, _ = _register_user("analytics_a")
    headers_user_b, _ = _register_user("analytics_b")

    # User A initiates a chat message (creates conversation & message)
    client.post(
        "/api/v1/chat/",
        json={"message": "tenant A message", "agent_type": "customer_service"},
        headers=headers_user_a,
    )

    # User B's summary should have 0 conversations and 0 messages
    resp_b_summary = client.get("/api/v1/analytics/summary", headers=headers_user_b)
    assert resp_b_summary.status_code == 200
    summary_b = resp_b_summary.json()
    assert summary_b["total_conversations"] == 0
    assert summary_b["total_messages"] == 0

    # User A's summary reflects User A's activity (at least 1 conversation)
    resp_a_summary = client.get("/api/v1/analytics/summary", headers=headers_user_a)
    assert resp_a_summary.status_code == 200
    summary_a = resp_a_summary.json()
    assert summary_a["total_conversations"] >= 1
    assert summary_a["total_messages"] >= 1
