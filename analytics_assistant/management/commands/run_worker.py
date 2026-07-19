import time
import logging
import traceback
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.db import transaction, models

from analytics_assistant.models import BackgroundJob
from analytics_assistant.jobs.handlers import JOB_HANDLERS

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Run the background job worker to process asynchronous tasks."

    def add_arguments(self, parser):
        parser.add_argument('--sleep', type=int, default=5, help='Sleep interval between polls')
        parser.add_argument('--once', action='store_true', help='Run one loop and exit')

    def handle(self, *args, **options):
        sleep_time = options['sleep']
        run_once = options['once']
        
        self.stdout.write(self.style.SUCCESS(f"Starting Background Job Worker (sleep={sleep_time}s)..."))
        
        while True:
            try:
                self.process_next_job()
            except Exception as e:
                logger.error(f"Worker encountered an error: {e}")
                
            if run_once:
                break
                
            time.sleep(sleep_time)
            
    def process_next_job(self):
        # We need to atomically claim the next available job
        with transaction.atomic():
            job = BackgroundJob.objects.select_for_update(skip_locked=True).filter(
                status="queued"
            ).filter(
                # Either no schedule, or schedule is in the past
                models.Q(scheduled_at__isnull=True) | models.Q(scheduled_at__lte=timezone.now())
            ).order_by('created_at').first()
            
            if not job:
                return
                
            job.status = "running"
            job.started_at = timezone.now()
            job.save(update_fields=["status", "started_at"])
            
        self.stdout.write(f"Processing Job {job.id} of type {job.job_type}")
        
        try:
            handler = JOB_HANDLERS.get(job.job_type)
            if not handler:
                raise ValueError(f"No handler found for job type: {job.job_type}")
                
            handler(job)
            
            job.status = "completed"
            job.progress = 100
            job.completed_at = timezone.now()
            job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
            job.save(update_fields=["status", "progress", "completed_at", "duration_seconds"])
            
            self.stdout.write(self.style.SUCCESS(f"Job {job.id} completed successfully."))
            
            self.schedule_next_recurrence(job)
            
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.error(f"Job {job.id} failed: {error_trace}")
            
            job.retry_count += 1
            if job.retry_count <= job.max_retries:
                job.status = "queued"
                job.error_message = str(e)
                # Exponential backoff or simple fixed backoff
                job.scheduled_at = timezone.now() + timedelta(minutes=5 * job.retry_count)
                self.stdout.write(self.style.WARNING(f"Job {job.id} failed, retrying at {job.scheduled_at}"))
            else:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = timezone.now()
                job.duration_seconds = (job.completed_at - job.started_at).total_seconds()
                self.stdout.write(self.style.ERROR(f"Job {job.id} failed permanently."))
                
            job.save(update_fields=["status", "error_message", "retry_count", "scheduled_at", "completed_at", "duration_seconds"])

    def schedule_next_recurrence(self, job: BackgroundJob):
        if job.recurrence == "none" or not job.recurrence:
            return
            
        next_schedule = None
        now = timezone.now()
        
        if job.recurrence == "hourly":
            next_schedule = now + timedelta(hours=1)
        elif job.recurrence == "daily":
            next_schedule = now + timedelta(days=1)
        elif job.recurrence == "weekly":
            next_schedule = now + timedelta(weeks=1)
        elif job.recurrence == "monthly":
            next_schedule = now + timedelta(days=30)
            
        if next_schedule:
            BackgroundJob.objects.create(
                job_type=job.job_type,
                status="queued",
                workspace=job.workspace,
                dataset_upload=job.dataset_upload,
                connector=job.connector,
                created_by=job.created_by,
                max_retries=job.max_retries,
                scheduled_at=next_schedule,
                recurrence=job.recurrence
            )
            self.stdout.write(f"Scheduled recurring job {job.job_type} for {next_schedule}")
