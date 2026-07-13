"""Request-scoped helpers: role resolution and dashboard state."""

from analytics_assistant.models import ChatSession, DashboardState
from analytics_assistant.roles import normalize_role


def role_from_request(request) -> str:
    if request.user.is_authenticated:
        group_names = {group.name.lower() for group in request.user.groups.all()}
        if "ceo" in group_names:
            return "ceo"
        if "marketing_manager" in group_names or "marketing" in group_names:
            return "marketing_manager"
        return "team_member"
    raw_role = request.GET.get("role") or (request.data or {}).get("role")
    return normalize_role(raw_role)


def resolve_dashboard_state(request) -> DashboardState:
    if request.user.is_authenticated:
        state, _ = DashboardState.objects.get_or_create(user=request.user)
        return state
    if not request.session.session_key:
        request.session.save()
    state, _ = DashboardState.objects.get_or_create(
        session_key=request.session.session_key, user=None
    )
    return state


def session_belongs_to_request(session: ChatSession, request) -> bool:
    if request.user.is_authenticated:
        return session.user_id == request.user.id
    # For anonymous users: session must be bound to the same browser session key.
    # Guard against requests without session middleware (e.g. RequestFactory in tests).
    raw_session = getattr(request, "session", None)
    request_session_key = (raw_session.session_key if raw_session else None) or ""
    return session.user_id is None and session.session_key == request_session_key

