import os
import re
import uuid
import logging
from pathlib import Path
import pandas as pd

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import DatasetUpload, DatasetVersion
from .data_loaders import load_tabular_from_path
from .schema import validate_dataset_columns
from .upload_service import persist_dataset_activation

# Import the new connector framework
from .connectors.registry import ConnectorRegistry

logger = logging.getLogger(__name__)

def test_connection(engine: str, config: dict) -> tuple[bool, str]:
    """Test a database connection via the connector registry."""
    try:
        connector = ConnectorRegistry.get_connector(engine)
        return connector.test_connection(config)
    except Exception as e:
        return False, str(e)

def discover_tables(engine: str, config: dict) -> list[str]:
    """Discover tables for a given database engine."""
    connector = ConnectorRegistry.get_connector(engine)
    return connector.discover_tables(config)

def fetch_table_data(engine: str, config: dict, table_name: str) -> pd.DataFrame:
    """Fetch table data using the specified engine's connector."""
    connector = ConnectorRegistry.get_connector(engine)
    return connector.fetch_table(config, table_name)

def sync_dataset_source(request, dataset_upload: DatasetUpload) -> dict:
    source_type = dataset_upload.source_type
    
    # Supported database engine source types
    db_engines = ConnectorRegistry.get_supported_engines()
    
    if source_type in db_engines:
        config = dataset_upload.connection_config
        table_name = config.get("table")
        if not table_name:
            logger.error("sync_dataset_source: No database table configured for this dataset.")
            raise ValueError("No database table configured for this dataset.")
            
        logger.info(f"sync_dataset_source: Pulling fresh table data for dataset_id={dataset_upload.id}, engine={source_type}, table={table_name}")
        # Pull fresh table data using the connector framework
        try:
            df = fetch_table_data(source_type, config, table_name)
            logger.info(f"sync_dataset_source: Fetched DataFrame with shape {df.shape}")
        except Exception as e:
            logger.error(f"sync_dataset_source: Failed to fetch table data: {str(e)}", exc_info=True)
            raise
        
        # Check for schema changes
        old_cols = [c["name"] for c in dataset_upload.ai_blueprint.get("columns", [])]
        new_cols = df.columns.tolist()
        schema_changed = set(old_cols) != set(new_cols)
        if schema_changed and old_cols:
            logger.warning(
                "Schema change detected during sync for dataset_id=%s. Old: %s, New: %s",
                dataset_upload.id, old_cols, new_cols
            )
            
        # Save table content to unique CSV file name in django storage
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", dataset_upload.name or f"{source_type}_dataset")
        csv_data = df.to_csv(index=False).encode("utf-8")
        storage_name = default_storage.save(
            f"datasets/{safe_name}_{uuid.uuid4().hex[:8]}.csv",
            ContentFile(csv_data)
        )
        stored_file_path = Path(settings.MEDIA_ROOT) / storage_name
        import_meta = {"format": source_type, "table": table_name}
        
        # Validate columns
        is_valid, missing, _ = validate_dataset_columns(df.columns.tolist())
        if not is_valid:
            logger.error(f"sync_dataset_source: Schema validation failed, missing columns: {missing}")
            raise ValueError(f"Schema validation failed: missing columns {', '.join(missing)}")
            
        # Run activation and save version
        logger.info(f"sync_dataset_source: Generating DatasetVersion via persist_dataset_activation")
        try:
            res = persist_dataset_activation(
                request,
                source_type=source_type,
                stored_path=stored_file_path,
                df=df,
                import_meta=import_meta,
                file_field=storage_name,
                name=dataset_upload.name,
                dataset_upload=dataset_upload,
            )
            logger.info(f"sync_dataset_source: Successfully activated dataset version for upload_id={dataset_upload.id}")
        except Exception as e:
            logger.error(f"sync_dataset_source: persist_dataset_activation failed: {str(e)}", exc_info=True)
            raise
        
        # Update last_sync_at
        dataset_upload.last_sync_at = timezone.now()
        dataset_upload.save(update_fields=["last_sync_at"])
        if schema_changed and old_cols:
            res["schema_changed"] = True
        return res
        
    elif source_type == "url":
        from .upload_service import fetch_url_content
        content, suffix = fetch_url_content(dataset_upload.source_url)
        temp_name = default_storage.save(f"datasets/sync_url_{uuid.uuid4().hex[:8]}{suffix}", ContentFile(content))
        temp_path = Path(settings.MEDIA_ROOT) / temp_name
        
        df, import_meta = load_tabular_from_path(temp_path)
        is_valid, missing, _ = validate_dataset_columns(df.columns.tolist())
        if not is_valid:
            raise ValueError(f"Schema validation failed: missing columns {', '.join(missing)}")
            
        res = persist_dataset_activation(
            request,
            source_type="url",
            stored_path=temp_path,
            df=df,
            import_meta=import_meta,
            source_url=dataset_upload.source_url,
            name=dataset_upload.name,
            dataset_upload=dataset_upload,
        )
        dataset_upload.last_sync_at = timezone.now()
        dataset_upload.save(update_fields=["last_sync_at"])
        return res
        
    elif source_type == "file":
        if not dataset_upload.file or not default_storage.exists(dataset_upload.file.name):
            raise FileNotFoundError("The uploaded file for this dataset was not found.")
            
        file_path = Path(settings.MEDIA_ROOT) / dataset_upload.file.name
        df, import_meta = load_tabular_from_path(file_path)
        is_valid, missing, _ = validate_dataset_columns(df.columns.tolist())
        if not is_valid:
            raise ValueError(f"Schema validation failed: missing columns {', '.join(missing)}")
            
        res = persist_dataset_activation(
            request,
            source_type="file",
            stored_path=file_path,
            df=df,
            import_meta=import_meta,
            file_field=dataset_upload.file.name,
            name=dataset_upload.name,
            dataset_upload=dataset_upload,
        )
        dataset_upload.last_sync_at = timezone.now()
        dataset_upload.save(update_fields=["last_sync_at"])
        return res
        
    else:
        raise ValueError(f"Unsupported sync source type: {source_type}")
