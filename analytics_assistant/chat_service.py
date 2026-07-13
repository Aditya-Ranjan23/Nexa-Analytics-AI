"""AI assistant chat orchestration."""

import logging

from django.conf import settings

from .analytics import build_analytics_payload
from .models import ChatMessage, ChatSession
from .request_context import session_belongs_to_request
from .services import ask_nvidia_assistant

logger = logging.getLogger(__name__)


def build_memory_context(session: ChatSession, max_items: int = 8) -> str:
    recent_messages = session.messages.order_by("-created_at")[:max_items]
    ordered = list(reversed(recent_messages))
    return "\n".join(f"{msg.role}: {msg.content}" for msg in ordered)


def resolve_chat_session(request, session_id, role: str, title: str) -> ChatSession:
    if session_id:
        session = ChatSession.objects.filter(id=session_id).first()
        if session and session_belongs_to_request(session, request):
            return session
        if session:
            logger.warning(
                "Rejected chat session %s for request user=%s",
                session_id,
                request.user.id if request.user.is_authenticated else "anonymous",
            )
    # Ensure Django session key exists before binding to anonymous session.
    if not request.user.is_authenticated and not request.session.session_key:
        request.session.save()
    return ChatSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        session_key="" if request.user.is_authenticated else (request.session.session_key or ""),
        role=role,
        title=title[:80],
    )


def process_chat(
    request,
    *,
    user_message: str,
    role: str,
    session_id=None,
    dataset_upload=None,
    blueprint_override=None,
) -> dict:
    session = resolve_chat_session(request, session_id, role, title=user_message)
    ChatMessage.objects.create(session=session, role="user", content=user_message)

    analytics_snapshot = build_analytics_payload(
        role=role,
        dataset_upload=dataset_upload,
        blueprint_override=blueprint_override,
    )
    answer = ask_nvidia_assistant(
        user_prompt=user_message,
        analytics_snapshot=analytics_snapshot,
        memory_context=build_memory_context(session),
    )
    ChatMessage.objects.create(session=session, role="assistant", content=answer)

    return {
        "reply": answer,
        "powered_by_nvidia": bool(settings.NVIDIA_API_KEY),
        "session_id": session.id,
        "role": role,
    }
