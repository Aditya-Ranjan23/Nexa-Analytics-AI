import os
import re
import uuid
import logging
from pathlib import Path
import pandas as pd
import psycopg

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from .models import DatasetUpload, DatasetVersion
from .crypto import decrypt_password
from .data_loaders import load_tabular_from_path
from .schema import validate_dataset_columns
from .upload_service import persist_dataset_activation

logger = logging.getLogger(__name__)

def get_postgres_connection(config: dict):
    password = decrypt_password(config.get("password", ""))
    conn = psycopg.connect(
        host=config.get("host"),
        port=int(config.get("port", 5432)),
        dbname=config.get("database"),
        user=config.get("username"),
        password=password,
        connect_timeout=5,
    )
    return conn

def test_postgres_connection(config: dict) -> tuple[bool, str]:
    try:
        conn = get_postgres_connection(config)
        conn.close()
        return True, "Connection successful."
    except Exception as e:
        return False, str(e)

def discover_postgres_tables(config: dict) -> list[str]:
    conn = get_postgres_connection(config)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
                ORDER BY table_name;
            """)
            tables = [row[0] for row in cur.fetchall()]
            return tables
    finally:
        conn.close()

def fetch_postgres_table_data(config: dict, table_name: str) -> pd.DataFrame:
    conn = get_postgres_connection(config)
    try:
        if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
            raise ValueError("Invalid table name characters.")
            
        with conn.cursor() as cur:
            cur.execute(f'SELECT * FROM "{table_name}"')
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description]
            df = pd.DataFrame(rows, columns=columns)
            return df
    finally:
        conn.close()

def sync_dataset_source(request, dataset_upload: DatasetUpload) -> dict:
    source_type = dataset_upload.source_type
    
    if source_type == "postgres":
        config = dataset_upload.connection_config
        table_name = config.get("table")
        if not table_name:
            raise ValueError("No database table configured for this dataset.")
            
        # Pull fresh table data
        df = fetch_postgres_table_data(config, table_name)
        
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
        safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", dataset_upload.name or "postgres_dataset")
        csv_data = df.to_csv(index=False).encode("utf-8")
        storage_name = default_storage.save(
            f"datasets/{safe_name}_{uuid.uuid4().hex[:8]}.csv",
            ContentFile(csv_data)
        )
        stored_file_path = Path(settings.MEDIA_ROOT) / storage_name
        import_meta = {"format": "postgres", "table": table_name}
        
        # Validate columns
        is_valid, missing, _ = validate_dataset_columns(df.columns.tolist())
        if not is_valid:
            raise ValueError(f"Schema validation failed: missing columns {', '.join(missing)}")
            
        # Run activation and save version
        res = persist_dataset_activation(
            request,
            source_type="postgres",
            stored_path=stored_file_path,
            df=df,
            import_meta=import_meta,
            file_field=storage_name,
            name=dataset_upload.name,
            dataset_upload=dataset_upload,
        )
        
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
