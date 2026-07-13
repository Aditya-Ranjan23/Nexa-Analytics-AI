"""Unified dataset resolution and loading (single source of truth)."""

import logging
from pathlib import Path

import pandas as pd
from django.conf import settings

from .data_loaders import load_tabular_from_path
from .models import DatasetUpload

logger = logging.getLogger(__name__)

DEFAULT_SEED_PATH = Path(settings.BASE_DIR) / "data" / "sales_data.csv"


def resolve_active_upload(dataset_upload: DatasetUpload | None = None) -> DatasetUpload | None:
    if dataset_upload and dataset_upload.stored_path:
        return dataset_upload
    return DatasetUpload.objects.filter(status="processed").order_by("-created_at").first()


def active_blueprint(
    dataset_upload: DatasetUpload | None = None, blueprint_override: dict | None = None
) -> dict:
    if blueprint_override:
        return blueprint_override
    upload = resolve_active_upload(dataset_upload)
    if upload:
        return upload.ai_blueprint or {}
    return {}


def load_dataframe_from_path(path: str | Path) -> pd.DataFrame | None:
    file_path = Path(path)
    if not file_path.exists():
        logger.warning("Dataset path missing: %s", file_path)
        return None
    if file_path.suffix.lower() in (".csv", ".xlsx", ".xls"):
        df, _ = load_tabular_from_path(file_path)
        return df
    return pd.read_csv(file_path)


def load_seed_dataset() -> pd.DataFrame:
    if not DEFAULT_SEED_PATH.exists():
        logger.warning("Default seed dataset missing at %s", DEFAULT_SEED_PATH)
        return pd.DataFrame()
    return pd.read_csv(DEFAULT_SEED_PATH)


def load_active_dataframe(dataset_upload: DatasetUpload | None = None) -> pd.DataFrame:
    """
    Resolution order:
    1. Explicit or latest processed upload (media/datasets/)
    2. PostgreSQL when ANALYTICS_SOURCE=postgres
    3. Bundled seed CSV (read-only default)
    """
    upload = resolve_active_upload(dataset_upload)
    if upload:
        df = load_dataframe_from_path(upload.stored_path)
        if df is not None:
            return df

    source = getattr(settings, "ANALYTICS_SOURCE", "csv")
    if source == "postgres":
        from .data_sources import get_data_source

        return get_data_source().load()

    return load_seed_dataset()
