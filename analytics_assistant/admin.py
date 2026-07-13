from django.contrib import admin

from .models import ChatMessage, ChatSession, DashboardState, DatasetUpload, IngestionJob


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "role", "user", "updated_at")
    search_fields = ("title", "user__username")
    list_filter = ("role",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "role", "created_at")
    search_fields = ("content",)
    list_filter = ("role",)


@admin.register(DatasetUpload)
class DatasetUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "source_type", "row_count", "status", "created_at")
    search_fields = ("source_url", "stored_path")
    list_filter = ("source_type", "status")


@admin.register(IngestionJob)
class IngestionJobAdmin(admin.ModelAdmin):
    list_display = ("id", "source", "status", "created_at")
    search_fields = ("source", "details")
    list_filter = ("status",)


@admin.register(DashboardState)
class DashboardStateAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "active_upload", "updated_at")
    search_fields = ("session_key", "user__username")
