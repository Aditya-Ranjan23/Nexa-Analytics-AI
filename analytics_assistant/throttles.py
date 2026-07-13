"""Scoped DRF throttle classes for resource-intensive endpoints.

These allow per-endpoint rate limits separate from the global anon/user rates.
They are applied with @throttle_classes([...]) in views.py.
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class ChatAnonThrottle(AnonRateThrottle):
    """Tighter anonymous rate limit for the AI chat endpoint."""

    scope = "chat_anon"


class ChatUserThrottle(UserRateThrottle):
    """Tighter authenticated rate limit for the AI chat endpoint."""

    scope = "chat_user"


class UploadAnonThrottle(AnonRateThrottle):
    """Tighter anonymous rate limit for file and URL upload endpoints."""

    scope = "upload_anon"


class UploadUserThrottle(UserRateThrottle):
    """Tighter authenticated rate limit for file and URL upload endpoints."""

    scope = "upload_user"
