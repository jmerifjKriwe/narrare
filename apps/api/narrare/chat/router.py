"""Chat router — SSE streaming + history CRUD.

Thin delegation layer (RULE-06): every route immediately delegates to
ChatService. No business logic lives here.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from narrare._app.dependencies import CurrentUserIdDep
from narrare.chat.dependencies import get_chat_service
from narrare.chat.schemas import (
    ChatDeleteResponse,
    ChatHistoryResponse,
    ChatMessageSchema,
    ChatRequest,
)

if TYPE_CHECKING:
    from narrare.chat.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
    request: ChatRequest,
    user_id: CurrentUserIdDep,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Stream a chat response via Server-Sent Events (SSE).

    The stream emits three event types:
    - ``meta``: Contains ``conversation_id`` and ``request_id``.
    - ``token``: A text fragment of the assistant's response.
    - ``done``: Signals completion with token usage stats.

    Args:
        request: The chat request (project_id, message, optional conversation_id).
        user_id: Authenticated user extracted from JWT.
        service: Injected ChatService instance.

    Returns:
        SSE streaming response.
    """
    # Convert the Pydantic schema to the core dataclass for the service
    from narrare_core.chat.contracts import ChatRequest as CoreChatRequest

    core_request = CoreChatRequest(
        project_id=request.project_id,
        message=request.message,
        conversation_id=request.conversation_id,
    )

    def _serialize_for_json(event: dict[str, object]) -> str:
        """Convert all non-string values to strings for SSE JSON."""
        return json.dumps({k: str(v) if not isinstance(v, str) else v for k, v in event.items()})

    async def event_stream():
        stream = await service.ask(core_request, UUID(user_id))
        async for event in stream:
            event_type = event.get("type", "")
            if event_type == "meta":
                yield f"event: meta\ndata: {_serialize_for_json(event)}\n\n"
            elif event_type == "token":
                yield f"event: token\ndata: {json.dumps(event)}\n\n"
            elif event_type == "done":
                yield f"event: done\ndata: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/history/{conversation_id}", response_model=ChatHistoryResponse)
async def get_history(
    conversation_id: UUID,
    user_id: CurrentUserIdDep,
    service: ChatService = Depends(get_chat_service),
) -> ChatHistoryResponse:
    """Get the full message history for a conversation.

    Args:
        conversation_id: UUID of the conversation to retrieve.
        user_id: Authenticated user extracted from JWT.
        service: Injected ChatService instance.

    Returns:
        ChatHistoryResponse with messages, timestamps, and project info.
    """
    messages = await service.get_history(conversation_id)
    project_id = await service.get_project_id_for_conversation(conversation_id)

    return ChatHistoryResponse(
        conversation_id=conversation_id,
        project_id=project_id if project_id is not None else UUID(int=0),
        messages=[
            ChatMessageSchema(
                message_id=m.conversation_id,
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.delete("/history/{conversation_id}", response_model=ChatDeleteResponse)
async def clear_history(
    conversation_id: UUID,
    user_id: CurrentUserIdDep,
    service: ChatService = Depends(get_chat_service),
) -> ChatDeleteResponse:
    """Clear all messages in a conversation.

    Args:
        conversation_id: UUID of the conversation to clear.
        user_id: Authenticated user extracted from JWT.
        service: Injected ChatService instance.

    Returns:
        ChatDeleteResponse confirming deletion.
    """
    await service.clear_history(conversation_id)
    return ChatDeleteResponse(conversation_id=conversation_id)
