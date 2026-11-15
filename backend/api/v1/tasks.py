from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from ...models.agent_models import AGENT_TYPE_VALUES
from ...models.task_models import TASK_PRIORITY_VALUES, TASK_STATUS_VALUES
from ...services import auth_service
from ...services.orchestration_service import (
    OrchestrationService,
    OrchestrationServiceError,
    get_orchestration_service,
)

router = APIRouter(
    prefix="/api/v1/tasks",
    tags=["tasks"],
    dependencies=[Depends(auth_service.get_current_user)],
)


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="pending", pattern="^(pending|in_progress|done|cancelled)$")
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    agent_type: Optional[str] = Field(
        default=None,
        pattern="^(customer_service|sales_research|content_creation|data_analysis|project_management)$",
    )
    workflow_instance_id: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, pattern="^(pending|in_progress|done|cancelled)$")
    priority: Optional[str] = Field(default=None, pattern="^(low|medium|high|urgent)$")
    assigned_to: Optional[int] = None
    due_date: Optional[datetime] = None
    agent_type: Optional[str] = Field(
        default=None,
        pattern="^(customer_service|sales_research|content_creation|data_analysis|project_management)$",
    )
    workflow_instance_id: Optional[str] = None


class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    assigned_to: Optional[int] = None
    created_by: int
    due_date: Optional[datetime] = None
    agent_type: Optional[str] = None
    workflow_instance_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


def _service() -> OrchestrationService:
    return get_orchestration_service()


@router.get("/", response_model=list[TaskRead])
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    assigned_to: Optional[int] = Query(default=None),
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    return await service.list_tasks(
        current_user_id=current_user.id,
        is_admin=bool(current_user.is_admin),
        skip=skip,
        limit=limit,
        status_filter=status_filter,
        assigned_to=assigned_to,
    )


@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreateRequest,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.create_task(
            payload.model_dump(),
            current_user_id=current_user.id,
        )
    except OrchestrationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{task_id}", response_model=TaskRead)
async def get_task(
    task_id: int,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.get_task(
            task_id,
            current_user_id=current_user.id,
            is_admin=bool(current_user.is_admin),
        )
    except OrchestrationServiceError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc).lower()
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: int,
    payload: TaskUpdateRequest,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.update_task(
            task_id,
            payload.model_dump(exclude_unset=True),
            current_user_id=current_user.id,
            is_admin=bool(current_user.is_admin),
        )
    except OrchestrationServiceError as exc:
        message = str(exc).lower()
        if "not found" in message:
            status_code = status.HTTP_404_NOT_FOUND
        elif "not authorized" in message:
            status_code = status.HTTP_403_FORBIDDEN
        else:
            status_code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        await service.delete_task(
            task_id,
            current_user_id=current_user.id,
            is_admin=bool(current_user.is_admin),
        )
    except OrchestrationServiceError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc).lower()
            else status.HTTP_403_FORBIDDEN
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
