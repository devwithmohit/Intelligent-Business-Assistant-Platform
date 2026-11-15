from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..services import auth_service
from ..services.orchestration_service import (
    OrchestrationServiceError,
    get_orchestration_service,
)

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws/chat/{conversation_id}")
async def chat_websocket(websocket: WebSocket, conversation_id: int) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        user = await auth_service.get_user_from_token(token)
    except auth_service.AuthError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    service = get_orchestration_service()
    try:
        conversation_detail = await service.get_conversation(user.id, conversation_id)
    except OrchestrationServiceError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    agent_type = conversation_detail["conversation"]["agent_type"]
    try:
        while True:
            message = await websocket.receive_text()
            if not message.strip():
                await websocket.send_text("")
                continue
            response = await service.send_chat_message(
                user_id=user.id,
                message=message,
                agent_type=agent_type,
                conversation_id=conversation_id,
                context={},
            )
            await websocket.send_text(response["reply"])
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
