import logging
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
import pandas as pd

from .analytics import build_analytics_payload
from .chat_service import process_chat
from .models import IngestionJob, DatasetUpload, DatasetVersion
from .request_context import resolve_dashboard_state, user_dataset_queryset, ownership_filter_kwargs
from .serializers import (
    BlueprintSerializer,
    ChatRequestSerializer,
    IngestionRunSerializer,
    UploadLinkSerializer,
    DatasetUploadSerializer,
    DatasetUpdateSerializer,
    DatasetVersionSerializer,
)
from .upload_service import (
    process_file_upload,
    process_url_upload,
    record_failed_upload,
)
from .dataset_pipeline import restore_dataset_version, load_dataframe_from_path

logger = logging.getLogger(__name__)


@ensure_csrf_cookie
def dashboard(request):
    return render(request, "analytics_assistant/dashboard.html")


@api_view(["GET"])
def analytics_summary(request):
    state = resolve_dashboard_state(request)
    payload = build_analytics_payload(
        dataset_upload=state.active_upload,
        blueprint_override=state.blueprint_override,
    )
    return Response(payload, status=status.HTTP_200_OK)


@api_view(["POST"])
def assistant_chat(request):
    serializer = ChatRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    state = resolve_dashboard_state(request)
    data = serializer.validated_data
    result = process_chat(
        request,
        user_message=data["message"],
        session_id=data.get("session_id"),
        dataset_upload=state.active_upload,
        blueprint_override=state.blueprint_override,
    )
    return Response(result, status=status.HTTP_200_OK)


@api_view(["POST"])
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


def get_dataset_or_404(request, pk):
    return get_object_or_404(user_dataset_queryset(request), pk=pk)


@api_view(["GET"])
def dataset_list(request):
    qs = user_dataset_queryset(request).order_by("-created_at")
    state = resolve_dashboard_state(request)
    serializer = DatasetUploadSerializer(
        qs, many=True,
        context={"request": request, "active_upload_id": state.active_upload_id},
    )
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["PATCH", "DELETE"])
def dataset_detail(request, pk):
    dataset = get_dataset_or_404(request, pk)
    if request.method == "PATCH":
        serializer = DatasetUpdateSerializer(dataset, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        full_serializer = DatasetUploadSerializer(dataset, context={"request": request})
        return Response(full_serializer.data, status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        state = resolve_dashboard_state(request)
        if state.active_upload_id == dataset.id:
            state.active_upload = None
            state.blueprint_override = {}
            state.save(update_fields=["active_upload", "blueprint_override", "updated_at"])

        # Clean parent files
        if dataset.file:
            try:
                dataset.file.delete(save=False)
            except Exception as e:
                logger.warning("Failed to delete FileField file: %s", e)
        if dataset.stored_path:
            import os
            try:
                if os.path.exists(dataset.stored_path):
                    os.remove(dataset.stored_path)
            except Exception as e:
                logger.warning("Failed to delete stored_path file: %s", e)

        # Clean all version files
        for version in dataset.versions.all():
            if version.file:
                try:
                    version.file.delete(save=False)
                except Exception as e:
                    logger.warning("Failed to delete version FileField file: %s", e)
            if version.stored_path:
                import os
                try:
                    if os.path.exists(version.stored_path):
                        os.remove(version.stored_path)
                except Exception as e:
                    logger.warning("Failed to delete version stored_path file: %s", e)

        dataset.delete()
        return Response({"detail": "Dataset deleted successfully."}, status=status.HTTP_200_OK)


@api_view(["POST"])
def dataset_activate(request, pk):
    dataset = get_dataset_or_404(request, pk)
    if dataset.status != "processed":
        return Response(
            {"detail": "Only successfully processed datasets can be activated."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if dataset.is_archived:
        return Response(
            {"detail": "Archived datasets cannot be activated. Unarchive it first."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    state = resolve_dashboard_state(request)
    state.active_upload = dataset
    state.blueprint_override = {}
    state.save(update_fields=["active_upload", "blueprint_override", "updated_at"])
    
    serializer = DatasetUploadSerializer(dataset, context={"request": request})
    return Response(
        {
            "detail": "Dataset activated.",
            "dataset": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def dataset_deactivate(request):
    state = resolve_dashboard_state(request)
    state.active_upload = None
    state.blueprint_override = {}
    state.save(update_fields=["active_upload", "blueprint_override", "updated_at"])
    return Response({"detail": "Dashboard reverted to default seed dataset."}, status=status.HTTP_200_OK)


@api_view(["POST"])
def dataset_archive(request, pk):
    dataset = get_dataset_or_404(request, pk)
    dataset.is_archived = not dataset.is_archived
    dataset.save(update_fields=["is_archived"])
    serializer = DatasetUploadSerializer(dataset, context={"request": request})
    status_str = "archived" if dataset.is_archived else "unarchived"
    return Response(
        {
            "detail": f"Dataset {status_str}.",
            "dataset": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
def dataset_versions_list(request, pk):
    dataset = get_dataset_or_404(request, pk)
    versions = dataset.versions.all().order_by("-version_number")
    serializer = DatasetVersionSerializer(versions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
def dataset_upload_version(request, pk):
    dataset = get_dataset_or_404(request, pk)
    upload = request.FILES.get("file")
    if not upload:
        return Response({"detail": "No file uploaded."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = process_file_upload(request, upload, dataset_upload=dataset)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("File upload failed for dataset version %s", dataset.id)
        return Response({"detail": "Upload failed."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def dataset_url_version(request, pk):
    dataset = get_dataset_or_404(request, pk)
    url = request.data.get("url")
    if not url:
        return Response({"detail": "No URL provided."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        result = process_url_upload(request, url, dataset_upload=dataset)
        return Response(result, status=status.HTTP_200_OK)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("URL ingestion failed for dataset version %s", dataset.id)
        return Response({"detail": "Ingestion failed."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def dataset_version_restore(request, pk, version_number):
    dataset = get_dataset_or_404(request, pk)
    version = get_object_or_404(dataset.versions, version_number=version_number)
    
    restore_dataset_version(dataset, version)
    
    # Reset dashboard override state so the restored dataset active configuration loads
    state = resolve_dashboard_state(request)
    state.blueprint_override = {}
    state.save(update_fields=["blueprint_override", "updated_at"])
    
    serializer = DatasetUploadSerializer(dataset, context={"request": request})
    return Response(
        {
            "detail": f"Dataset restored to version {version_number}.",
            "dataset": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
def dataset_version_compare(request, pk):
    dataset = get_dataset_or_404(request, pk)
    
    v1_num = request.GET.get("v1")
    v2_num = request.GET.get("v2")
    
    if not v1_num or not v2_num:
        return Response(
            {"detail": "Both v1 and v2 version numbers are required query parameters."},
            status=status.HTTP_400_BAD_REQUEST,
        )
        
    try:
        v1_num = int(v1_num)
        v2_num = int(v2_num)
    except ValueError:
        return Response(
            {"detail": "v1 and v2 parameters must be integers."},
            status=status.HTTP_400_BAD_REQUEST,
        )
        
    version_1 = get_object_or_404(dataset.versions, version_number=v1_num)
    version_2 = get_object_or_404(dataset.versions, version_number=v2_num)
    
    df1 = load_dataframe_from_path(version_1.stored_path)
    df2 = load_dataframe_from_path(version_2.stored_path)
    
    if df1 is None or df2 is None:
        return Response(
            {"detail": "Could not load dataset files for comparison."},
            status=status.HTTP_400_BAD_REQUEST,
        )
        
    cols1 = set(df1.columns)
    cols2 = set(df2.columns)
    
    added = list(cols2 - cols1)
    removed = list(cols1 - cols2)
    common = list(cols1 & cols2)
    
    # Calculate numeric difference for common numeric columns
    numeric_compare = {}
    for col in common:
        if pd.api.types.is_numeric_dtype(df1[col]) and pd.api.types.is_numeric_dtype(df2[col]):
            try:
                # Drop nulls for statistics
                col_v1 = df1[col].dropna()
                col_v2 = df2[col].dropna()
                
                v1_mean = float(col_v1.mean()) if not col_v1.empty else 0.0
                v2_mean = float(col_v2.mean()) if not col_v2.empty else 0.0
                
                numeric_compare[col] = {
                    "v1_mean": v1_mean,
                    "v2_mean": v2_mean,
                    "mean_diff": v2_mean - v1_mean,
                    "v1_min": float(col_v1.min()) if not col_v1.empty else 0.0,
                    "v2_min": float(col_v2.min()) if not col_v2.empty else 0.0,
                    "v1_max": float(col_v1.max()) if not col_v1.empty else 0.0,
                    "v2_max": float(col_v2.max()) if not col_v2.empty else 0.0,
                }
            except Exception as e:
                logger.warning("Could not calculate stats for column %s: %s", col, e)
                
    payload = {
        "v1_metadata": {
            "version_number": v1_num,
            "row_count": len(df1),
            "created_at": version_1.created_at,
        },
        "v2_metadata": {
            "version_number": v2_num,
            "row_count": len(df2),
            "created_at": version_2.created_at,
        },
        "row_count_diff": len(df2) - len(df1),
        "columns_diff": {
            "added": added,
            "removed": removed,
            "common": common,
        },
        "numeric_stats_compare": numeric_compare,
    }
    
    return Response(payload, status=status.HTTP_200_OK)


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
        "version": "0.3.0",
        "checks": {
            "database": "ok" if db_ok else f"error: {db_error}",
        },
    }
    http_status = 200 if db_ok else 503
    return JsonResponse(payload, status=http_status)