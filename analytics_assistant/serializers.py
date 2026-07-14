from rest_framework import serializers
from .models import DatasetUpload, DatasetVersion


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(trim_whitespace=True, max_length=4000)
    role = serializers.CharField(required=False, allow_blank=True, max_length=32)
    session_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    def validate_message(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("Please provide a message.")
        return value


class UploadLinkSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=2048)


class BlueprintSerializer(serializers.Serializer):
    blueprint = serializers.DictField()


class IngestionRunSerializer(serializers.Serializer):
    source = serializers.CharField(required=False, allow_blank=True, max_length=64)


class DatasetUploadSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = DatasetUpload
        fields = [
            "id",
            "name",
            "display_name",
            "description",
            "source_type",
            "row_count",
            "status",
            "error_message",
            "is_archived",
            "active_version_number",
            "created_at",
            "is_active",
        ]

    def get_is_active(self, obj) -> bool:
        # Prefer pre-resolved id from context (avoids N+1 DB hit per row).
        active_id = self.context.get("active_upload_id")
        if active_id is not None:
            return active_id == obj.id
        # Fallback for single-object serialization (detail views).
        request = self.context.get("request")
        if not request:
            return False
        from .request_context import resolve_dashboard_state
        state = resolve_dashboard_state(request)
        return state.active_upload_id == obj.id


class DatasetUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DatasetUpload
        fields = ["name", "description"]


class DatasetVersionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = DatasetVersion
        fields = [
            "id",
            "version_number",
            "name",
            "description",
            "source_type",
            "row_count",
            "created_at",
            "is_active",
        ]

    def get_is_active(self, obj) -> bool:
        # A version is active if its version_number matches the parent dataset's active_version_number.
        return obj.dataset.active_version_number == obj.version_number
