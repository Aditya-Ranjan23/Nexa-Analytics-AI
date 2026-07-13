import logging

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response

from .analytics import build_analytics_payload
from .chat_service import process_chat
from .models import IngestionJob
from .request_context import resolve_dashboard_state, role_from_request
from .serializers import (
    BlueprintSerializer,
    ChatRequestSerializer,
    IngestionRunSerializer,
    UploadLinkSerializer,
)
from .throttles import ChatAnonThrottle, ChatUserThrottle, UploadAnonThrottle, UploadUserThrottle
from .upload_service import process_file_upload, process_url_upload, record_failed_upload

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def dashboard(request):
    return render(request, "analytics_assistant/dashboard.html")


@api_view(["GET"])
def analytics_summary(request):
    role = role_from_request(request)
    state = resolve_dashboard_state(request)
    payload = build_analytics_payload(
        role=role,
        dataset_upload=state.active_upload,
        blueprint_override=state.blueprint_override,
    )
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
@throttle_classes([ChatAnonThrottle, ChatUserThrottle])
def assistant_chat(request):
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    role = role_from_request(request)
    state = resolve_dashboard_state(request)
    data = serializer.validated_data
    result = process_chat(
        request,
        user_message=data["message"],
        role=role,
        session_id=data.get("session_id"),
        dataset_upload=state.active_upload,
        blueprint_override=state.blueprint_override,
    )
    return Response(result, status=status.HTTP_200_OK)


@api_view(["GET"])
def role_dashboard(request):
    role = role_from_request(request)
    state = resolve_dashboard_state(request)
    payload = build_analytics_payload(
        role=role,
        dataset_upload=state.active_upload,
        blueprint_override=state.blueprint_override,
    )
    return Response(
        {
            "role": role,
            "widgets": payload["widgets"],
            "kpis": payload["kpis"],
            "top_dimensions": payload.get("top_dimensions", []),
            "dataset_mode": payload.get("dataset_mode", "generic"),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@throttle_classes([UploadAnonThrottle, UploadUserThrottle])
def dataset_upload(request):
    upload = request.FILES.get("file")
    if not upload:
        return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = process_file_upload(request, upload)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Schema validation failed"):
            missing = detail.split(":", 1)[-1].strip()
            return Response(
                {"detail": "Schema validation failed.", "missing_columns": missing.split(", ")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("File upload failed for %s", upload.name)
        record_failed_upload(
            source_type="file",
            error_message=str(exc),
        )
        return Response({"detail": "Upload failed. Please check the file format."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@throttle_classes([UploadAnonThrottle, UploadUserThrottle])
def dataset_upload_link(request):
    serializer = UploadLinkSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    source_url = serializer.validated_data["url"]
    try:
        result = process_url_upload(request, source_url)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("Schema validation failed"):
            missing = detail.split(":", 1)[-1].strip()
            return Response(
                {"detail": "Schema validation failed.", "missing_columns": missing.split(", ")},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("URL dataset ingestion failed for %s", source_url)
        record_failed_upload(source_type="url", source_url=source_url, error_message=str(exc))
        return Response({"detail": "Ingestion failed. Please verify the URL."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def run_ingestion(request):
    serializer = IngestionRunSerializer(data=request.data or {})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    source = serializer.validated_data.get("source", "").strip() or "manual"
    try:
        state = resolve_dashboard_state(request)
        payload = build_analytics_payload(
            role="team_member",
            dataset_upload=state.active_upload,
            blueprint_override=state.blueprint_override,
        )
        job = IngestionJob.objects.create(
            source=source,
            status="success",
            details=f"Active dataset rows: {payload['records']}",
        )
        return Response(
            {
                "detail": "Ingestion job completed.",
                "job_id": job.id,
                "records": payload["records"],
            },
            status=status.HTTP_200_OK,
        )
    except Exception as exc:
        logger.exception("Ingestion job failed source=%s", source)
        job = IngestionJob.objects.create(source=source, status="failed", details=str(exc))
        return Response(
            {"detail": f"Ingestion failed: {exc}", "job_id": job.id},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET", "POST"])
def dashboard_blueprint(request):
    state = resolve_dashboard_state(request)
    if request.method == "GET":
        active = state.active_upload
        return Response(
            {
                "active_upload_id": active.id if active else None,
                "stored_blueprint": active.ai_blueprint if active else {},
                "override_blueprint": state.blueprint_override or {},
                "effective_blueprint": state.blueprint_override
                if state.blueprint_override
                else (active.ai_blueprint if active else {}),
            },
            status=status.HTTP_200_OK,
        )

    serializer = BlueprintSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    state.blueprint_override = serializer.validated_data["blueprint"]
    state.save(update_fields=["blueprint_override", "updated_at"])
    return Response({"detail": "Blueprint saved."}, status=status.HTTP_200_OK)


def health_check(request):
    """Liveness + shallow readiness check.

    Returns 200 when the app is running and the database is reachable.
    Returns 503 when the database ping fails so load-balancers can route away.
    """
    from django.db import connection, OperationalError

    db_ok = True
    db_error = None
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except OperationalError as exc:
        db_ok = False
        db_error = str(exc)
        logger.error("Health check DB ping failed: %s", exc)

    payload = {
        "status": "ok" if db_ok else "degraded",
        "version": "0.2.0",
        "checks": {
            "database": "ok" if db_ok else f"error: {db_error}",
        },
    }
    http_status = 200 if db_ok else 503
    return JsonResponse(payload, status=http_status)