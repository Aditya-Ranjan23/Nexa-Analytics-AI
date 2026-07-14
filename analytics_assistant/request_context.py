"""Request-scoped helpers: workspace resolution and dashboard state."""

from analytics_assistant.models import ChatSession, DashboardState, DatasetUpload, Workspace


def resolve_active_workspace(request) -> Workspace | None:
    """Resolve the active Workspace for an authenticated user, creating a default on the fly if needed."""
    if not request.user.is_authenticated:
        return None
    workspace = request.user.workspaces.first()
    if not workspace:
        workspace = Workspace.objects.create(
            owner=request.user,
            name=f"{request.user.username}'s Workspace"
        )
    return workspace


def resolve_dashboard_state(request) -> DashboardState:
    if request.user.is_authenticated:
        workspace = resolve_active_workspace(request)
        state, _ = DashboardState.objects.get_or_create(workspace=workspace, user=request.user)
        return state
    if not request.session.session_key:
        request.session.save()
    state, _ = DashboardState.objects.get_or_create(
        session_key=request.session.session_key, user=None, workspace=None
    )
    return state


def ownership_filter_kwargs(request) -> dict:
    """Return ORM filter kwargs that scope models by Workspace or session key."""
    if request.user.is_authenticated:
        workspace = resolve_active_workspace(request)
        return {"workspace": workspace}
    if not request.session.session_key:
        request.session.save()
    return {"session_key": request.session.session_key, "workspace": None}


def user_dataset_queryset(request):
    """Return a DatasetUpload queryset scoped to the requesting user/session."""
    return DatasetUpload.objects.filter(**ownership_filter_kwargs(request))


def session_belongs_to_request(session: ChatSession, request) -> bool:
    if request.user.is_authenticated:
        workspace = resolve_active_workspace(request)
        return session.workspace_id == workspace.id
    # For anonymous users: session must be bound to the same browser session key.
    # Guard against requests without session middleware (e.g. RequestFactory in tests).
    raw_session = getattr(request, "session", None)
    request_session_key = (raw_session.session_key if raw_session else None) or ""
    return session.user_id is None and session.session_key == request_session_key
