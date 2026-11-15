from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from ...services import auth_service
from ...services.orchestration_service import (
    OrchestrationService,
    OrchestrationServiceError,
    get_orchestration_service,
)

router = APIRouter(
    prefix="/api/v1/chat",
    tags=["chat"],
    dependencies=[Depends(auth_service.get_current_user)],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    agent_type: str
    conversation_id: Optional[int] = None
    context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int


class ConversationRead(BaseModel):
    id: int
    user_id: int
    agent_type: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    tokens_used: Optional[int] = None
    model: Optional[str] = None
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation: ConversationRead
    messages: list[MessageRead]


def _service() -> OrchestrationService:
    return get_orchestration_service()


@router.post("/", response_model=ChatResponse)
async def send_message(
    payload: ChatRequest,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.send_chat_message(
            user_id=current_user.id,
            message=payload.message,
            agent_type=payload.agent_type,
            conversation_id=payload.conversation_id,
            context=payload.context,
        )
    except OrchestrationServiceError as exc:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in str(exc).lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    return await service.list_conversations(
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: int,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        return await service.get_conversation(current_user.id, conversation_id)
    except OrchestrationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: int,
    current_user=Depends(auth_service.get_current_user),
    service: OrchestrationService = Depends(_service),
):
    try:
        await service.delete_conversation(current_user.id, conversation_id)
    except OrchestrationServiceError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
