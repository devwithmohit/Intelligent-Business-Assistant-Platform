from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class JobCreate(BaseModel):
    job_type: str = Field(..., description="Type of background job (e.g., workflow_execution, agent_run)")
    resource_id: Optional[str] = Field(default=None, description="Identifier of the resource being processed")
    payload: dict[str, Any] = Field(default_factory=dict, description="Input parameters for the background job")


class JobRead(BaseModel):
    id: str
    user_id: int
    job_type: str
    status: str
    resource_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AsyncDispatchResponse(BaseModel):
    job_id: str
    status: str = "queued"
    message: str = "Task successfully queued for background execution"
    resource_id: Optional[str] = None
