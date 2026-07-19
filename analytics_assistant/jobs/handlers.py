import logging
from django.utils import timezone
from analytics_assistant.models import BackgroundJob
from analytics_assistant.connector_pipeline import sync_dataset_source

logger = logging.getLogger(__name__)

def handle_sync_dataset(job: BackgroundJob):
    """
    Handler for 'sync_dataset' job type.
    """
    dataset = job.dataset_upload
    if not dataset:
        raise ValueError("No dataset_upload provided for sync_dataset job.")
    
    # We call sync_dataset_source but pass request=None.
    # The sync_dataset_source itself uses request to pass to persist_dataset_activation.
    # We need to make sure sync_dataset_source works with request=None.
    res = sync_dataset_source(None, dataset)
    
    job.result_metadata = res
    job.save(update_fields=["result_metadata"])

def handle_process_upload(job: BackgroundJob):
    """
    Handler for 'process_upload' job type.
    This runs the SmartDataPreparationEngine on uploaded datasets.
    """
    dataset = job.dataset_upload
    if not dataset:
        raise ValueError("No dataset_upload provided for process_upload job.")
        
    job.current_stage = "Loading raw dataset..."
    job.progress = 10
    job.save(update_fields=["current_stage", "progress"])
    
    from analytics_assistant.data_loaders import load_tabular_from_path
    from analytics_assistant.schema import validate_dataset_columns
    from analytics_assistant.upload_service import record_failed_upload, persist_dataset_activation
    from analytics_assistant.data_preparation import SmartDataPreparationEngine
    
    try:
        from pathlib import Path
        df, import_meta = load_tabular_from_path(Path(dataset.stored_path))
    except Exception as e:
        raise ValueError(f"Failed to read file: {str(e)}")
        
    job.current_stage = "Validating dataset..."
    job.progress = 30
    job.save(update_fields=["current_stage", "progress"])
    
    is_valid, missing, _mode = validate_dataset_columns(df.columns.tolist())
    if not is_valid:
        raise ValueError(f"Schema validation failed: {', '.join(missing)}")
        
    job.current_stage = "Cleaning dataset..."
    job.progress = 50
    job.save(update_fields=["current_stage", "progress"])
    
    engine = SmartDataPreparationEngine()
    cleaned_df, report = engine.prepare(df)
    
    if len(report.get("validation_errors", [])) > 0 and cleaned_df.empty:
        raise ValueError(f"Preparation failed: {', '.join(report['validation_errors'])}")
        
    # Save cleaned dataframe to disk
    import tempfile
    import os
    from pathlib import Path
    from django.conf import settings
    
    clean_path = Path(settings.MEDIA_ROOT) / "datasets" / f"clean_{dataset.id}_{os.path.basename(dataset.stored_path)}"
    
    job.current_stage = "Saving cleaned dataset..."
    job.progress = 70
    job.save(update_fields=["current_stage", "progress"])
    
    # ensure dir exists
    clean_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save as CSV natively to preserve types as best as possible
    cleaned_df.to_csv(clean_path, index=False)
    
    job.current_stage = "Generating intelligent insights..."
    job.progress = 85
    job.save(update_fields=["current_stage", "progress"])
    
    # Activate and generate insights
    result = persist_dataset_activation(
        request=None,
        source_type=dataset.source_type,
        stored_path=clean_path,
        df=cleaned_df,
        import_meta=import_meta,
        file_field=dataset.file.name if dataset.file else "",
        name=dataset.name,
        dataset_upload=dataset,
    )
    
    # Inject the cleaning report into the active version
    from analytics_assistant.models import DatasetVersion
    active_ver = DatasetVersion.objects.filter(dataset=dataset).order_by('-version_number').first()
    if active_ver:
        active_ver.cleaning_report = report
        active_ver.save(update_fields=["cleaning_report"])
    
    job.current_stage = "Dataset Ready"
    job.progress = 100
    job.result_metadata = result
    job.save(update_fields=["current_stage", "progress", "result_metadata"])


# Registry of job handlers
JOB_HANDLERS = {
    "sync_dataset": handle_sync_dataset,
    "process_upload": handle_process_upload,
}
