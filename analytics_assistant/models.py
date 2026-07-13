from django.conf import settings
from django.db import models


class ChatSession(models.Model):
    ROLE_CHOICES = (
        ("ceo", "CEO"),
        ("marketing_manager", "Marketing Manager"),
        ("team_member", "Team Member"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=32, choices=ROLE_CHOICES, default="team_member")
    title = models.CharField(max_length=120, default="New conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.role} - {self.title}"


class ChatMessage(models.Model):
    session = models.ForeignKey(
        ChatSession, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16)  # user or assistant
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class DatasetUpload(models.Model):
    SOURCE_CHOICES = (
        ("file", "File"),
        ("url", "URL"),
    )

    source_type = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    file = models.FileField(upload_to="datasets/", null=True, blank=True)
    source_url = models.URLField(blank=True, default="")
    stored_path = models.CharField(max_length=255, blank=True, default="")
    row_count = models.IntegerField(default=0)
    ai_blueprint = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, default="processed")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source_type} upload #{self.id}"


class IngestionJob(models.Model):
    source = models.CharField(max_length=32, default="manual")
    status = models.CharField(max_length=24, default="success")
    details = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} - {self.status}"


class DashboardState(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_states",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=64, blank=True, default="")
    active_upload = models.ForeignKey(
        DatasetUpload, on_delete=models.SET_NULL, null=True, blank=True
    )
    blueprint_override = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"state:{self.user_id or self.session_key}"
