from django.conf import settings
from django.db import models
from django.utils.text import slugify


class Organization(models.Model):
    """Top-level tenant. Every dataset, session, and dashboard belongs to one org."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    settings_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class OrganizationMember(models.Model):
    """Membership record linking a Django user to an organization with a role."""

    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("admin", "Admin"),
        ("analyst", "Analyst"),
        ("viewer", "Viewer"),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="org_memberships",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default="analyst")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("organization", "user")]
        ordering = ["organization", "user"]

    def __str__(self):
        return f"{self.user} @ {self.organization} ({self.role})"


class ChatSession(models.Model):
    ROLE_CHOICES = (
        ("ceo", "CEO"),
        ("marketing_manager", "Marketing Manager"),
        ("team_member", "Team Member"),
    )

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_sessions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_sessions",
        null=True,
        blank=True,
    )
    session_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
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

    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="datasets",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_datasets",
    )
    session_key = models.CharField(max_length=64, blank=True, default="", db_index=True)
    name = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    source_type = models.CharField(max_length=16, choices=SOURCE_CHOICES)
    file = models.FileField(upload_to="datasets/", null=True, blank=True)
    source_url = models.URLField(blank=True, default="")
    stored_path = models.CharField(max_length=255, blank=True, default="")
    row_count = models.IntegerField(default=0)
    ai_blueprint = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=24, default="processed")
    error_message = models.TextField(blank=True, default="")
    is_archived = models.BooleanField(default=False)
    active_version_number = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def display_name(self) -> str:
        """Human-readable label for datasets that pre-date the name field."""
        if self.name:
            return self.name
        if self.source_url:
            from pathlib import Path
            from urllib.parse import urlparse
            stem = Path(urlparse(self.source_url).path).stem
            return stem or self.source_url[:60]
        if self.stored_path:
            from pathlib import Path
            return Path(self.stored_path).stem
        return f"Dataset #{self.id}"

    def __str__(self):
        return self.display_name


class DatasetVersion(models.Model):
    dataset = models.ForeignKey(DatasetUpload, on_delete=models.CASCADE, related_name="versions")
    version_number = models.IntegerField()
    name = models.CharField(max_length=200, blank=True, default="")
    description = models.TextField(blank=True, default="")
    source_type = models.CharField(max_length=16, choices=DatasetUpload.SOURCE_CHOICES)
    file = models.FileField(upload_to="datasets/versions/", null=True, blank=True)
    source_url = models.URLField(blank=True, default="")
    stored_path = models.CharField(max_length=255, blank=True, default="")
    row_count = models.IntegerField(default=0)
    ai_blueprint = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("dataset", "version_number"),)
        ordering = ["dataset", "-version_number"]

    def __str__(self):
        return f"{self.dataset.display_name} - v{self.version_number}"


class IngestionJob(models.Model):
    source = models.CharField(max_length=32, default="manual")
    status = models.CharField(max_length=24, default="success")
    details = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.source} - {self.status}"


class DashboardState(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dashboard_states",
    )
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
