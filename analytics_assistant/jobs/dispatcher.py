import logging
from django.utils import timezone
from analytics_assistant.models import BackgroundJob

logger = logging.getLogger(__name__)

def enqueue_job(
    job_type: str, 
    workspace, 
    dataset_upload=None, 
    connector="", 
    created_by=None, 
    scheduled_at=None, 
    recurrence="none"
) -> BackgroundJob:
    """
    Safely enqueues a new background job.
    """
    job = BackgroundJob.objects.create(
        job_type=job_type,
        status="queued",
        workspace=workspace,
        dataset_upload=dataset_upload,
        connector=connector,
        created_by=created_by,
        scheduled_at=scheduled_at,
        recurrence=recurrence
    )
    logger.info(f"Enqueued job {job.id} of type {job_type}")
    return job
