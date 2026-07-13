from rest_framework import serializers


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
