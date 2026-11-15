from __future__ import annotations

from backend.services.orchestration_service import OrchestrationService


def test_chat_routes_create_and_fetch_conversation(client, auth_headers, monkeypatch):
    async def fake_run_agent(self, agent_type, input_text, user_id, context=None, conversation_id=None):
        return {
            "success": True,
            "output": f"stub reply for {agent_type}: {input_text}",
            "error": None,
            "data": {"duration_ms": 1},
        }

    monkeypatch.setattr(OrchestrationService, "run_agent", fake_run_agent)

    response = client.post(
        "/api/v1/chat/",
        headers=auth_headers,
        json={
            "message": "Hello support",
            "agent_type": "customer_service",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["reply"].startswith("stub reply")

    conversation_id = payload["conversation_id"]
    detail_response = client.get(
        f"/api/v1/chat/conversations/{conversation_id}",
        headers=auth_headers,
    )
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()
    assert len(detail["messages"]) >= 2


def test_task_crud_routes(client, auth_headers):
    create_response = client.post(
        "/api/v1/tasks/",
        headers=auth_headers,
        json={
            "title": "Follow up with customer",
            "description": "Reply with the new plan",
            "priority": "high",
        },
    )
    assert create_response.status_code == 201, create_response.text
    task = create_response.json()

    list_response = client.get("/api/v1/tasks/", headers=auth_headers)
    assert list_response.status_code == 200, list_response.text
    assert any(item["id"] == task["id"] for item in list_response.json())

    update_response = client.patch(
        f"/api/v1/tasks/{task['id']}",
        headers=auth_headers,
        json={"status": "in_progress"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["status"] == "in_progress"

    delete_response = client.delete(
        f"/api/v1/tasks/{task['id']}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204, delete_response.text
