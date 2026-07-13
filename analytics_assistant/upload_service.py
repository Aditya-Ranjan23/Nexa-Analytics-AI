"""Dataset upload, activation, and URL ingestion."""

import logging
import mimetypes
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

from .data_loaders import load_tabular_from_path
from .dataset_profile import profile_for_blueprint
from .models import DatasetUpload
from .request_context import resolve_dashboard_state
from .schema import validate_dataset_columns
from .services import generate_dashboard_blueprint
from .url_safety import build_safe_session, validate_public_http_url

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = (".csv", ".xlsx", ".xls")
_ALLOWED_MIME_TYPES = frozenset({
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",  # common fallback for binary files served without type
})
# Default: 25 MB; override via MAX_UPLOAD_BYTES in settings / environment.
MAX_UPLOAD_BYTES: int = getattr(settings, "MAX_UPLOAD_BYTES", 25 * 1024 * 1024)


def _validate_upload_size(size_bytes: int, label: str = "Upload") -> None:
    """Raise ValueError if the file exceeds the configured size limit."""
    if size_bytes > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ValueError(f"{label} exceeds the maximum allowed size of {mb} MB.")


def _validate_mime_type(path: Path) -> None:
    """Raise ValueError if the file's MIME type is not in the allowed set."""
    mime, _ = mimetypes.guess_type(str(path))
    if mime and mime.lower() not in _ALLOWED_MIME_TYPES:
        raise ValueError(
            f"File type '{mime}' is not allowed. Upload CSV or Excel files only."
        )


def import_detail(import_meta: dict) -> str:
    sheets = import_meta.get("sheets_used") or []
    strategy = import_meta.get("strategy", "single")
    if strategy == "merged" and len(sheets) > 1:
        return f"Merged {len(sheets)} sheets: {', '.join(sheets)}"
    if sheets:
        return f"Using worksheet: {sheets[0]}"
    return "Dataset imported"


def activate_dataset(df: pd.DataFrame, import_meta: dict | None = None) -> tuple[int, dict, str]:
    profile = profile_for_blueprint(df)
    if import_meta:
        profile["import_meta"] = import_meta
    blueprint = generate_dashboard_blueprint(profile)
    if import_meta:
        blueprint["import_meta"] = import_meta
    mode = "ads" if validate_dataset_columns(df.columns.tolist())[2] == "ads" else "generic"
    return len(df), blueprint, mode


def persist_dataset_activation(
    request,
    *,
    source_type: str,
    stored_path: Path,
    df: pd.DataFrame,
    import_meta: dict,
    file_field: str = "",
    source_url: str = "",
) -> dict:
    row_count, blueprint, mode = activate_dataset(df, import_meta)
    create_kwargs = {
        "source_type": source_type,
        "stored_path": str(stored_path),
        "row_count": row_count,
        "ai_blueprint": blueprint,
        "status": "processed",
    }
    if file_field:
        create_kwargs["file"] = file_field
    if source_url:
        create_kwargs["source_url"] = source_url

    upload_record = DatasetUpload.objects.create(**create_kwargs)
    state = resolve_dashboard_state(request)
    state.active_upload = upload_record
    state.blueprint_override = {}
    state.save(update_fields=["active_upload", "blueprint_override", "updated_at"])
    logger.info(
        "Dataset activated upload_id=%s rows=%s mode=%s source=%s path=%s",
        upload_record.id,
        row_count,
        mode,
        source_type,
        stored_path,
    )
    verb = "uploaded" if source_type == "file" else "URL ingested"
    return {
        "detail": f"Dataset {verb} and activated. {import_detail(import_meta)}",
        "upload_id": upload_record.id,
        "rows": row_count,
        "dataset_mode": mode,
        "import_meta": import_meta,
        "blueprint": blueprint,
    }


def record_failed_upload(**kwargs) -> DatasetUpload:
    return DatasetUpload.objects.create(status="failed", **kwargs)


def process_file_upload(request, upload: UploadedFile) -> dict:
    suffix = Path(upload.name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise ValueError("Only CSV or Excel files are allowed.")

    # Size check before writing to disk.
    _validate_upload_size(upload.size, label="File")

    storage_name = default_storage.save(f"datasets/{upload.name}", upload)
    stored_file_path = Path(settings.MEDIA_ROOT) / storage_name

    # MIME type check on the saved file.
    _validate_mime_type(stored_file_path)

    df, import_meta = load_tabular_from_path(stored_file_path)
    is_valid, missing, _mode = validate_dataset_columns(df.columns.tolist())
    if not is_valid:
        record_failed_upload(
            source_type="file",
            file=storage_name,
            stored_path=str(stored_file_path),
            error_message=f"Missing columns: {', '.join(missing)}",
        )
        raise ValueError(f"Schema validation failed: {', '.join(missing)}")

    return persist_dataset_activation(
        request,
        source_type="file",
        stored_path=stored_file_path,
        df=df,
        import_meta=import_meta,
        file_field=storage_name,
    )


def fetch_url_content(source_url: str) -> tuple[bytes, str]:
    safe_url = validate_public_http_url(source_url)
    session = build_safe_session()
    response = session.get(safe_url, timeout=40)
    response.raise_for_status()
    # Size check on remote content before accepting.
    content_length = len(response.content)
    _validate_upload_size(content_length, label="Remote file")
    suffix = ".xlsx" if ".xlsx" in safe_url.lower() else ".csv"
    return response.content, suffix


def process_url_upload(request, source_url: str) -> dict:
    content, suffix = fetch_url_content(source_url)
    temp_name = default_storage.save(f"datasets/from_url{suffix}", ContentFile(content))
    temp_path = Path(settings.MEDIA_ROOT) / temp_name

    df, import_meta = load_tabular_from_path(temp_path)
    is_valid, missing, _mode = validate_dataset_columns(df.columns.tolist())
    if not is_valid:
        record_failed_upload(
            source_type="url",
            source_url=source_url,
            stored_path=str(temp_path),
            error_message=f"Missing columns: {', '.join(missing)}",
        )
        raise ValueError(f"Schema validation failed: {', '.join(missing)}")

    return persist_dataset_activation(
        request,
        source_type="url",
        stored_path=temp_path,
        df=df,
        import_meta=import_meta,
        source_url=source_url,
    )
