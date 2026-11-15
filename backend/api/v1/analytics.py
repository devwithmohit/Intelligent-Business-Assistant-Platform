from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...services import auth_service
from ...services.orchestration_service import (
    OrchestrationService,
    OrchestrationServiceError,
    get_orchestration_service,
)

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"],
    dependencies=[Depends(auth_service.get_current_user)],
)


class AnalyticsSummary(BaseModel):
    total_conversations: int
    total_messages: int
    agents_active: int


class AgentAnalyticsRow(BaseModel):
    agent_type: str
    runs: int
    success_rate: float
    avg_latency_ms: int


class UsageRow(BaseModel):
    date: str
    conversations: int
    messages: int


def _service() -> OrchestrationService:
    return get_orchestration_service()


@router.get("/summary", response_model=AnalyticsSummary)
async def analytics_summary(
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    """Return analytics summary scoped to the authenticated tenant."""
    try:
        return await service.get_summary(user_id=current_user.id)
    except OrchestrationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/agents", response_model=list[AgentAnalyticsRow])
async def analytics_agents(
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    """Return agent execution metrics scoped to the authenticated tenant."""
    return await service.get_agent_metrics(user_id=current_user.id)


@router.get("/usage", response_model=list[UsageRow])
async def analytics_usage(
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    """Return timeline usage analytics scoped to the authenticated tenant."""
    return await service.get_usage(user_id=current_user.id)
