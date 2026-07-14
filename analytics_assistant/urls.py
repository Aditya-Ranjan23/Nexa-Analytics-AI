from django.urls import path

from .views import (
    analytics_summary,
    assistant_chat,
    dashboard,
    dashboard_blueprint,
    dataset_upload,
    dataset_upload_link,
    health_check,
    run_ingestion,
    dataset_list,
    dataset_detail,
    dataset_activate,
    dataset_deactivate,
    dataset_archive,
    dataset_versions_list,
    dataset_upload_version,
    dataset_url_version,
    dataset_version_restore,
    dataset_version_compare,
)

urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("api/analytics/summary/", analytics_summary, name="analytics_summary"),
    path("api/chat/", assistant_chat, name="assistant_chat"),
    path("api/dashboard/blueprint/", dashboard_blueprint, name="dashboard_blueprint"),
    path("api/data/upload/", dataset_upload, name="dataset_upload"),
    path("api/data/upload-link/", dataset_upload_link, name="dataset_upload_link"),
    path("api/ingestion/run/", run_ingestion, name="run_ingestion"),
    
    # Dataset Management
    path("api/data/datasets/", dataset_list, name="dataset_list"),
    path("api/data/datasets/<int:pk>/", dataset_detail, name="dataset_detail"),
    path("api/data/datasets/<int:pk>/activate/", dataset_activate, name="dataset_activate"),
    path("api/data/datasets/deactivate/", dataset_deactivate, name="dataset_deactivate"),
    path("api/data/datasets/<int:pk>/archive/", dataset_archive, name="dataset_archive"),
    
    # Dataset Versioning & History
    path("api/data/datasets/<int:pk>/versions/", dataset_versions_list, name="dataset_versions_list"),
    path("api/data/datasets/<int:pk>/versions/upload/", dataset_upload_version, name="dataset_upload_version"),
    path("api/data/datasets/<int:pk>/versions/url/", dataset_url_version, name="dataset_url_version"),
    path("api/data/datasets/<int:pk>/versions/<int:version_number>/restore/", dataset_version_restore, name="dataset_version_restore"),
    path("api/data/datasets/<int:pk>/versions/compare/", dataset_version_compare, name="dataset_version_compare"),
    
    path("health/", health_check, name="health_check"),
]
