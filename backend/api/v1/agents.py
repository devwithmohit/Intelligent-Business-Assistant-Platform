from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ...services import auth_service
from ...services.orchestration_service import (
    OrchestrationService,
    OrchestrationServiceError,
    get_orchestration_service,
)

router = APIRouter(
    prefix="/api/v1/agents",
    tags=["agents"],
    dependencies=[Depends(auth_service.get_current_user)],
)


class AgentInfoResponse(BaseModel):
    type: str
    name: str
    status: str
    last_run_at: Optional[datetime] = None


class AgentRunRequest(BaseModel):
    input: str = Field(..., min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)


class AgentRunResponse(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None


class AgentRunLog(BaseModel):
    agent_id: str
    agent_type: str
    timestamp: int
    payload: dict[str, Any] = Field(default_factory=dict)
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0


def _service() -> OrchestrationService:
    return get_orchestration_service()


@router.get("/", response_model=list[AgentInfoResponse])
async def list_agents(
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    return await service.list_agent_statuses(getattr(current_user, "id", None))


@router.get("/{agent_type}", response_model=AgentInfoResponse)
async def get_agent(
    agent_type: str,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.get_agent_status(
            agent_type,
            getattr(current_user, "id", None),
        )
    except OrchestrationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{agent_type}/run", response_model=AgentRunResponse)
async def run_agent(
    agent_type: str,
    payload: AgentRunRequest,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.run_agent(
            agent_type=agent_type,
            input_text=payload.input,
            user_id=current_user.id,
            context=payload.context,
        )
    except OrchestrationServiceError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{agent_type}/history", response_model=list[AgentRunLog])
async def agent_history(
    agent_type: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.list_agent_history(
            agent_type, user_id=current_user.id, skip=skip, limit=limit
        )
    except OrchestrationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
