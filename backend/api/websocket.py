from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from ..services import auth_service
from ..services.orchestration_service import (
    OrchestrationServiceError,
    get_orchestration_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/api/ws/chat/{conversation_id}")
async def chat_websocket(websocket: WebSocket, conversation_id: int) -> None:
    """
    Secure WebSocket endpoint for real-time conversation chat.
    Does NOT accept JWTs in URL query parameters to avoid secret leakage in server/proxy logs.
    Enforces an immediate in-band authentication handshake frame upon connection establishment.
    """
    await websocket.accept()

    # Step 1: In-band authentication handshake frame
    try:
        raw_auth = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning(
            "WebSocket auth handshake timed out for conversation %s",
            conversation_id,
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication handshake timeout",
        )
        return
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("WebSocket error during initial handshake")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Handshake failure",
        )
        return

    # Extract token from the handshake frame
    token: str | None = None
    try:
        parsed_auth = json.loads(raw_auth)
        if isinstance(parsed_auth, dict):
            token = parsed_auth.get("token")
    except (json.JSONDecodeError, TypeError):
        # Fallback for plain string token frame
        token = raw_auth.strip() if raw_auth.strip() else None

    if not token:
        logger.warning(
            "WebSocket rejected: Missing token in authentication handshake frame for conversation %s",
            conversation_id,
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Missing authentication token",
        )
        return

    # Validate authentication credentials
    try:
        user = await auth_service.get_user_from_token(token)
    except (auth_service.AuthError, Exception):
        logger.warning(
            "WebSocket rejected: Invalid authentication credentials for conversation %s",
            conversation_id,
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid authentication credentials",
        )
        return

    # Verify conversation ownership / authorization
    service = get_orchestration_service()
    try:
        conversation_detail = await service.get_conversation(user.id, conversation_id)
    except OrchestrationServiceError:
        logger.warning(
            "WebSocket rejected: Conversation %s not found or access denied for user %s",
            conversation_id,
            user.id,
        )
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Conversation not found or access denied",
        )
        return

    # Acknowledge successful authentication handshake
    await websocket.send_json(
        {
            "type": "auth_success",
            "status": "authenticated",
            "conversation_id": conversation_id,
        }
    )

    agent_type = conversation_detail["conversation"]["agent_type"]

    # Step 2: Main chat message loop
    try:
        while True:
            raw_msg = await websocket.receive_text()
            if not raw_msg.strip():
                await websocket.send_text("")
                continue

            # Support both plain text strings and structured JSON payloads
            chat_text = raw_msg
            try:
                msg_payload = json.loads(raw_msg)
                if isinstance(msg_payload, dict):
                    if msg_payload.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                        continue
                    if "content" in msg_payload:
                        chat_text = str(msg_payload["content"])
                    elif "message" in msg_payload:
                        chat_text = str(msg_payload["message"])
            except (json.JSONDecodeError, TypeError):
                pass

            if not chat_text.strip():
                continue

            response = await service.send_chat_message(
                user_id=user.id,
                message=chat_text,
                agent_type=agent_type,
                conversation_id=conversation_id,
                context={},
            )
            await websocket.send_text(response["reply"])
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception(
            "Unexpected error in WebSocket message loop for conversation %s",
            conversation_id,
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
