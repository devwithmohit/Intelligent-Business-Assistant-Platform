import pytest

from backend.services.orchestration_service import OrchestrationService


@pytest.mark.asyncio
async def test_list_agent_statuses_creates_default_records():
    service = OrchestrationService()
    statuses = await service.list_agent_statuses()

    agent_types = {item["type"] for item in statuses}
    assert "customer_service" in agent_types
    assert "project_management" in agent_types


@pytest.mark.asyncio
async def test_run_agent_route_payload_mapping(monkeypatch):
    service = OrchestrationService()

    class DummyAgent:
        id = "runtime-1"

    async def fake_create_agent(agent_type, name, config):
        return DummyAgent()

    async def fake_run_agent(agent_id, payload):
        assert agent_id == "runtime-1"
        assert payload["question"] == "What changed?"
        assert payload["dataset"] == {"rows": 4}

        class Result:
            success = True
            output = "analysis complete"
            error = None
            data = {"duration_ms": 12}

        return Result()

    async def fake_run_db(fn, *args, **kwargs):
        return None

    monkeypatch.setattr(service.agent_service, "create_agent", fake_create_agent)
    monkeypatch.setattr(service.agent_service, "run_agent", fake_run_agent)
    monkeypatch.setattr(service, "_run_db", fake_run_db)

    result = await service.run_agent(
        agent_type="data_analysis",
        input_text="What changed?",
        user_id=1,
        context={"dataset": {"rows": 4}},
    )

    assert result["success"] is True
    assert result["output"] == "analysis complete"
