from __future__ import annotations

import pytest

from backend.services.orchestration_service import (
    OrchestrationService,
    OrchestrationServiceError,
)


def test_build_agent_payload_maps_customer_service():
    service = OrchestrationService()

    payload = service._build_agent_payload(
        "customer_service",
        "Where is my order?",
        {"customer_id": "cust-1"},
        14,
    )

    assert payload["customer_message"] == "Where is my order?"
    assert payload["customer_id"] == "cust-1"
    assert payload["conversation_id"] == 14


def test_invalid_task_transition_raises():
    service = OrchestrationService()

    with pytest.raises(OrchestrationServiceError):
        service._validate_task_transition("done", "in_progress")
