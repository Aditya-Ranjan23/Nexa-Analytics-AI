from django.urls import path

from .views import (
    analytics_summary,
    assistant_chat,
    dashboard,
    dashboard_blueprint,
    dataset_upload,
    dataset_upload_link,
    health_check,
    role_dashboard,
    run_ingestion,
)

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("api/analytics/summary/", analytics_summary, name="analytics_summary"),
    path("api/dashboard/role/", role_dashboard, name="role_dashboard"),
    path("api/chat/", assistant_chat, name="assistant_chat"),
    path("api/dashboard/blueprint/", dashboard_blueprint, name="dashboard_blueprint"),
    path("api/data/upload/", dataset_upload, name="dataset_upload"),
    path("api/data/upload-link/", dataset_upload_link, name="dataset_upload_link"),
    path("api/ingestion/run/", run_ingestion, name="run_ingestion"),
    path("health/", health_check, name="health_check"),
]
