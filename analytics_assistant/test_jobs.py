from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
import uuid

from analytics_assistant.models import BackgroundJob, Workspace, DatasetUpload
from analytics_assistant.jobs.dispatcher import enqueue_job
from analytics_assistant.jobs.handlers import JOB_HANDLERS

User = get_user_model()

class BackgroundJobTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="jobuser", password="password")
        self.workspace = Workspace.objects.create(owner=self.user, name="Job Workspace")
        self.client = APIClient()
        self.client.login(username="jobuser", password="password")

    def test_enqueue_job(self):
        job = enqueue_job("test_job", self.workspace, created_by=self.user)
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.job_type, "test_job")
        self.assertEqual(job.workspace, self.workspace)
        self.assertEqual(BackgroundJob.objects.count(), 1)

    def test_job_list_api(self):
        enqueue_job("test_job1", self.workspace, created_by=self.user)
        enqueue_job("test_job2", self.workspace, created_by=self.user)
        
        response = self.client.get("/api/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)

    def test_job_cancel_api(self):
        job = enqueue_job("test_job", self.workspace, created_by=self.user)
        response = self.client.post(f"/api/jobs/{job.id}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job.refresh_from_db()
        self.assertEqual(job.status, "cancelled")

    def test_job_retry_api(self):
        job = enqueue_job("test_job", self.workspace, created_by=self.user)
        job.status = "failed"
        job.save()
        
        response = self.client.post(f"/api/jobs/{job.id}/retry/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        job.refresh_from_db()
        self.assertEqual(job.status, "queued")
        self.assertEqual(job.progress, 0)
        
    def test_worker_processes_job(self):
        from django.core.management import call_command
        job = enqueue_job("sync_dataset", self.workspace, created_by=self.user)
        # Hack the handler for test
        JOB_HANDLERS["sync_dataset"] = lambda j: j
        
        call_command("run_worker", once=True, sleep=0)
        
        job.refresh_from_db()
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.progress, 100)
