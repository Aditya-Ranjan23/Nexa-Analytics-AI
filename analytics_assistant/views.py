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

from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect

from django.contrib.auth.views import LoginView

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = UserCreationForm.Meta.fields + ("email",)

class CustomLoginView(LoginView):
    template_name = "registration/login.html"

    def get(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        if request.user.is_authenticated:
            return redirect("dashboard")
        return redirect("/?auth=login")

    def post(self, request, *args, **kwargs):
        self.anon_session_key = request.session.session_key
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        remember_me = self.request.POST.get("remember_me")
        if remember_me:
            # 2 weeks
            self.request.session.set_expiry(1209600)
        else:
            # Browser close
            self.request.session.set_expiry(0)
        
        response = super().form_valid(form)
        
        if getattr(self, "anon_session_key", None):
            from .request_context import resolve_active_workspace
            workspace = resolve_active_workspace(self.request)
            DatasetUpload.objects.filter(
                session_key=self.anon_session_key,
                workspace__isnull=True
            ).update(workspace=workspace, owner=self.request.user)
            
        return response


def register(request):
    from django.shortcuts import redirect
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        anon_session_key = request.session.session_key
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            from .request_context import resolve_active_workspace
            dummy_req = type("Req", (), {"user": user})()
            workspace = resolve_active_workspace(dummy_req)

            from django.contrib.auth import login as auth_login
            auth_login(request, user)
            
            if anon_session_key:
                DatasetUpload.objects.filter(
                    session_key=anon_session_key,
                    workspace__isnull=True
                ).update(workspace=workspace, owner=user)
                
            return redirect("dashboard")
    
    return redirect("/?auth=register")


@ensure_csrf_cookie
def dashboard(request):
    state = resolve_dashboard_state(request)
    has_datasets = False
    if request.user.is_authenticated:
        from .request_context import resolve_active_workspace
        ws = resolve_active_workspace(request)
        has_datasets = ws.datasets.filter(is_archived=False).exists()
    else:
        # Check anonymous datasets
        has_datasets = DatasetUpload.objects.filter(
            session_key=request.session.session_key or "",
            workspace__isnull=True,
            is_archived=False
        ).exists()

    context = {
        "active_upload": state.active_upload,
        "has_datasets": has_datasets,
    }
    return render(request, "analytics_assistant/dashboard.html", context)


@api_view(["GET"])
def analytics_summary(request):
    state = resolve_dashboard_state(request)
    payload = build_analytics_payload(
        dataset_upload=state.active_upload,
        blueprint_override=state.blueprint_override,
    )
    
    if state.active_upload:
        payload["dataset_id"] = state.active_upload.id
        payload["dataset_name"] = state.active_upload.name or state.active_upload.display_name
        payload["source_type"] = state.active_upload.source_type
        payload["last_sync_at"] = state.active_upload.last_sync_at.isoformat() if state.active_upload.last_sync_at else None
        payload["active_version_number"] = state.active_upload.active_version_number
        payload["dataset_version"] = state.active_upload.active_version_number

        active_ver = state.active_upload.versions.filter(
            version_number=state.active_upload.active_version_number
        ).first()
        if active_ver:
            if not active_ver.insights_cache:
                from .dataset_pipeline import load_active_dataframe
                from .intelligent_analytics import run_intelligent_analytics
                df = load_active_dataframe(state.active_upload)
                insights = run_intelligent_analytics(
                    df,
                    state.active_upload.name or state.active_upload.display_name,
                    state.active_upload.source_type
                )
                active_ver.insights_cache = insights
                active_ver.save(update_fields=["insights_cache"])
            payload["proactive_insights"] = active_ver.insights_cache
        else:
            payload["proactive_insights"] = {}
    else:
        payload["dataset_id"] = None
        payload["dataset_name"] = "Seed Dataset"
        payload["source_type"] = "seed"
        payload["last_sync_at"] = None
        payload["active_version_number"] = 1
        payload["dataset_version"] = 1

        from .dataset_pipeline import load_active_dataframe
        from .intelligent_analytics import run_intelligent_analytics
        df = load_active_dataframe(None)
        payload["proactive_insights"] = run_intelligent_analytics(df, "Seed Dataset", "seed")
        
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
        "version": "0.6.0",
        "checks": {
            "database": "ok" if db_ok else f"error: {db_error}",
        },
    }
    http_status = 200 if db_ok else 503
    return JsonResponse(payload, status=http_status)


@api_view(["POST"])
def update_profile(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
    profile = request.user.profile

    display_name = request.data.get("display_name")
    bio = request.data.get("bio")
    timezone = request.data.get("timezone")
    avatar = request.FILES.get("avatar")

    if display_name is not None:
        profile.display_name = display_name
    if bio is not None:
        profile.bio = bio
    if timezone is not None:
        profile.timezone = timezone
    if avatar is not None:
        profile.avatar = avatar

    profile.save()

    email = request.data.get("email")
    if email is not None:
        request.user.email = email
        request.user.save()

    return Response({
        "display_name": profile.display_name,
        "email": request.user.email,
        "bio": profile.bio,
        "timezone": profile.timezone,
        "avatar_url": profile.avatar.url if profile.avatar else None,
        "detail": "Profile updated successfully"
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
def update_settings(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)
    profile = request.user.profile

    theme_preference = request.data.get("theme_preference")
    if theme_preference is not None:
        profile.theme_preference = theme_preference
        profile.save()

    return Response({
        "theme_preference": profile.theme_preference,
        "detail": "Settings updated successfully"
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
def export_account_data(request):
    from django.http import HttpResponse
    import json
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    user = request.user
    profile = user.profile

    export_data = {
        "user": {
            "username": user.username,
            "email": user.email,
            "display_name": profile.display_name,
            "bio": profile.bio,
            "timezone": profile.timezone,
            "theme_preference": profile.theme_preference,
            "date_joined": user.date_joined.isoformat() if user.date_joined else "",
        },
        "workspaces": [],
    }

    for ws in user.workspaces.all():
        ws_data = {
            "name": ws.name,
            "created_at": ws.created_at.isoformat() if ws.created_at else "",
            "datasets": [],
            "chat_sessions": [],
        }
        for ds in ws.datasets.all():
            ws_data["datasets"].append({
                "name": ds.name,
                "description": ds.description,
                "source_type": ds.source_type,
                "row_count": ds.row_count,
                "status": ds.status,
                "created_at": ds.created_at.isoformat() if ds.created_at else "",
            })
        for sess in ws.chat_sessions.all():
            sess_data = {
                "title": sess.title,
                "role": sess.role,
                "created_at": sess.created_at.isoformat() if sess.created_at else "",
                "messages": [],
            }
            for msg in sess.messages.all():
                sess_data["messages"].append({
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                })
            ws_data["chat_sessions"].append(sess_data)
        export_data["workspaces"].append(ws_data)

    return Response(export_data, status=status.HTTP_200_OK)


@api_view(["POST"])
def delete_account(request):
    if not request.user.is_authenticated:
        return Response({"detail": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

    user = request.user
    from django.contrib.auth import logout
    logout(request)
    user.delete()
    return Response({"deleted": True, "detail": "Account deleted successfully"}, status=status.HTTP_200_OK)


@api_view(["POST"])
def test_connector_connection(request):
    host = request.data.get("host")
    port = request.data.get("port", 5432)
    username = request.data.get("username")
    password = request.data.get("password", "")
    database = request.data.get("database")

    if not all([host, username, database]):
        return Response({"error": "Host, username, and database name are required."}, status=status.HTTP_400_BAD_REQUEST)

    from .crypto import encrypt_password
    from .connector_pipeline import test_postgres_connection

    config = {
        "host": host,
        "port": port,
        "username": username,
        "password": encrypt_password(password),
        "database": database,
    }

    success, message = test_postgres_connection(config)
    if success:
        return Response({"success": True, "message": message}, status=status.HTTP_200_OK)
    else:
        return Response({"success": False, "message": message}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def get_connector_schema(request):
    host = request.data.get("host")
    port = request.data.get("port", 5432)
    username = request.data.get("username")
    password = request.data.get("password", "")
    database = request.data.get("database")

    if not all([host, username, database]):
        return Response({"error": "Host, username, and database name are required."}, status=status.HTTP_400_BAD_REQUEST)

    from .crypto import encrypt_password
    from .connector_pipeline import discover_postgres_tables

    config = {
        "host": host,
        "port": port,
        "username": username,
        "password": encrypt_password(password),
        "database": database,
    }

    try:
        tables = discover_postgres_tables(config)
        return Response({"tables": tables}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def ingest_connector_table(request):
    host = request.data.get("host")
    port = request.data.get("port", 5432)
    username = request.data.get("username")
    password = request.data.get("password", "")
    database = request.data.get("database")
    table = request.data.get("table")
    name = request.data.get("name")

    if not all([host, username, database, table, name]):
        return Response({"error": "All fields, including database table and name, are required."}, status=status.HTTP_400_BAD_REQUEST)

    from pathlib import Path
    import re
    import uuid
    from django.conf import settings
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from .crypto import encrypt_password
    from .connector_pipeline import fetch_postgres_table_data
    from .schema import validate_dataset_columns
    from .upload_service import persist_dataset_activation

    config = {
        "host": host,
        "port": port,
        "username": username,
        "password": encrypt_password(password),
        "database": database,
        "table": table,
    }

    try:
        df = fetch_postgres_table_data(config, table)
        is_valid, missing, _ = validate_dataset_columns(df.columns.tolist())
        if not is_valid:
            return Response({"error": f"Schema validation failed: missing columns {', '.join(missing)}"}, status=status.HTTP_400_BAD_REQUEST)

        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        csv_data = df.to_csv(index=False).encode("utf-8")
        storage_name = default_storage.save(
            f"datasets/{safe_name}_{uuid.uuid4().hex[:8]}.csv",
            ContentFile(csv_data)
        )
        stored_file_path = Path(settings.MEDIA_ROOT) / storage_name
        import_meta = {"format": "postgres", "table": table}

        res = persist_dataset_activation(
            request,
            source_type="postgres",
            stored_path=stored_file_path,
            df=df,
            import_meta=import_meta,
            file_field=storage_name,
            name=name,
        )

        dataset_id = res.get("upload_id")
        if dataset_id:
            dataset_upload = DatasetUpload.objects.get(id=dataset_id)
            dataset_upload.connection_config = config
            dataset_upload.save(update_fields=["connection_config"])

        return Response(res, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def sync_dataset(request, pk):
    from .request_context import user_dataset_queryset
    dataset = get_object_or_404(user_dataset_queryset(request), pk=pk)

    from .connector_pipeline import sync_dataset_source
    try:
        res = sync_dataset_source(request, dataset)
        return Response(res, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def api_login(request):
    from django.contrib.auth import authenticate, login as auth_login
    username = request.data.get("username")
    password = request.data.get("password")
    remember_me = request.data.get("remember_me", False)

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

    user = authenticate(username=username, password=password)
    if user is not None:
        anon_session_key = request.session.session_key
        auth_login(request, user)

        if remember_me:
            request.session.set_expiry(1209600)  # 2 weeks
        else:
            request.session.set_expiry(0)        # Browser close

        # Claim anonymous datasets
        if anon_session_key:
            from .request_context import resolve_active_workspace
            workspace = resolve_active_workspace(request)
            DatasetUpload.objects.filter(
                session_key=anon_session_key,
                workspace__isnull=True
            ).update(workspace=workspace, owner=user)

        return Response({"success": True, "detail": "Logged in successfully."}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def api_register(request):
    form = CustomUserCreationForm(request.data)
    if form.is_valid():
        anon_session_key = request.session.session_key
        user = form.save()
        
        # Provision default workspace
        from .request_context import resolve_active_workspace
        dummy_req = type("Req", (), {"user": user})()
        workspace = resolve_active_workspace(dummy_req)

        from django.contrib.auth import login as auth_login
        auth_login(request, user)

        if anon_session_key:
            DatasetUpload.objects.filter(
                session_key=anon_session_key,
                workspace__isnull=True
            ).update(workspace=workspace, owner=user)

        return Response({"success": True, "detail": "Registered successfully."}, status=status.HTTP_201_CREATED)
    else:
        errors = []
        for field, errmsgs in form.errors.items():
            for msg in errmsgs:
                errors.append(f"{field.capitalize()}: {msg}")
        err_str = " ".join(errors) or "Registration failed."
        return Response({"error": err_str}, status=status.HTTP_400_BAD_REQUEST)


def custom_logout(request):
    from django.contrib.auth import logout
    from django.shortcuts import redirect
    logout(request)
    return redirect("/")


@api_view(["GET"])
def compare_version_insights(request, pk):
    from .request_context import user_dataset_queryset
    dataset = get_object_or_404(user_dataset_queryset(request), pk=pk)
    
    v1_num = request.GET.get("v1")
    v2_num = request.GET.get("v2")
    if not v1_num or not v2_num:
        return Response({"error": "Parameters v1 and v2 are required."}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        v1 = dataset.versions.get(version_number=int(v1_num))
        v2 = dataset.versions.get(version_number=int(v2_num))
    except (ValueError, DatasetVersion.DoesNotExist):
        return Response({"error": "One or both specified versions do not exist."}, status=status.HTTP_404_NOT_FOUND)

    from .dataset_pipeline import load_active_dataframe
    from .intelligent_analytics import run_intelligent_analytics
    
    # Version 1 cache
    if not v1.insights_cache:
        old_path = dataset.stored_path
        dataset.stored_path = v1.stored_path
        try:
            df = load_active_dataframe(dataset)
            v1.insights_cache = run_intelligent_analytics(df, dataset.name or dataset.display_name, v1.source_type)
            v1.save(update_fields=["insights_cache"])
        finally:
            dataset.stored_path = old_path
        
    # Version 2 cache
    if not v2.insights_cache:
        old_path = dataset.stored_path
        dataset.stored_path = v2.stored_path
        try:
            df = load_active_dataframe(dataset)
            v2.insights_cache = run_intelligent_analytics(df, dataset.name or dataset.display_name, v2.source_type)
            v2.save(update_fields=["insights_cache"])
        finally:
            dataset.stored_path = old_path

    return Response({
        "v1_number": v1.version_number,
        "v2_number": v2.version_number,
        "v1": v1.insights_cache,
        "v2": v2.insights_cache
    }, status=status.HTTP_200_OK)