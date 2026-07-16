import socket

from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from django.test.client import RequestFactory
from rest_framework.test import APIClient
import pandas as pd

from analytics_assistant.analytics import build_analytics_payload
from analytics_assistant.chart_engine import time_series_rows
from analytics_assistant.dataset_pipeline import (
    active_blueprint,
    load_active_dataframe,
    load_seed_dataset,
    resolve_active_upload,
)
from analytics_assistant.dataset_profile import profile_for_blueprint
from analytics_assistant.models import ChatSession, DatasetUpload, DatasetVersion
from analytics_assistant.request_context import session_belongs_to_request
from analytics_assistant.schema import validate_dataset_columns
from analytics_assistant.url_safety import (
    validate_public_http_url,
    validate_resolved_addresses,
)
from config.env_validation import (
    INSECURE_DEV_SECRET_KEY,
    is_insecure_secret_key,
    validate_deployment_env,
)


class SchemaTests(SimpleTestCase):
    def test_rejects_single_column(self):
        valid, missing, mode = validate_dataset_columns(["only_one"])
        self.assertFalse(valid)
        self.assertEqual(mode, "invalid")

    def test_detects_ads_mode(self):
        columns = [
            "date",
            "channel",
            "revenue",
            "orders",
            "ad_spend",
            "conversion_rate",
        ]
        valid, missing, mode = validate_dataset_columns(columns)
        self.assertTrue(valid)
        self.assertEqual(mode, "ads")
        self.assertEqual(missing, [])

    def test_generic_mode_for_partial_schema(self):
        valid, missing, mode = validate_dataset_columns(["date", "sales"])
        self.assertTrue(valid)
        self.assertEqual(mode, "generic")





class UrlSafetyTests(SimpleTestCase):
    def test_blocks_localhost(self):
        with self.assertRaises(ValueError):
            validate_public_http_url("http://localhost/data.csv")

    def test_blocks_private_ip_literal(self):
        with self.assertRaises(ValueError):
            validate_public_http_url("http://192.168.1.10/data.csv")

    def test_blocks_embedded_credentials(self):
        with self.assertRaises(ValueError):
            validate_public_http_url("http://user:pass@example.com/data.csv")

    def test_blocks_hostname_resolving_to_private_ip(self):
        def _evil_resolver(hostname, port, *args, **kwargs):
            self.assertEqual(hostname, "evil.example")
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0))]

        with self.assertRaises(ValueError) as ctx:
            validate_public_http_url("http://evil.example/data.csv", resolver=_evil_resolver)
        self.assertIn("private or reserved", str(ctx.exception).lower())

    def test_allows_hostname_resolving_to_public_ip(self):
        def _public_resolver(hostname, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        result = validate_public_http_url(
            "https://example.com/data.csv", resolver=_public_resolver
        )
        self.assertEqual(result, "https://example.com/data.csv")

    def test_blocks_unresolvable_hostname(self):
        def _fail_resolver(hostname, port, *args, **kwargs):
            raise socket.gaierror("Name or service not known")

        with self.assertRaises(ValueError) as ctx:
            validate_public_http_url("http://does-not-exist.invalid/data.csv", resolver=_fail_resolver)
        self.assertIn("resolve", str(ctx.exception).lower())

    def test_validate_resolved_addresses_blocks_private(self):
        with self.assertRaises(ValueError):
            validate_resolved_addresses(["192.168.0.1"])

    def test_allows_public_https_url_with_mock_resolver(self):
        def _public_resolver(hostname, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        self.assertEqual(
            validate_public_http_url("https://example.com/data.csv", resolver=_public_resolver),
            "https://example.com/data.csv",
        )


class AnalyticsEngineTests(SimpleTestCase):
    def test_time_series_rows_returns_tuple_on_empty_data(self):
        df = pd.DataFrame({"date": ["bad-date"], "sales": [None]})
        rows, x_key = time_series_rows(df, "date", "sales")
        self.assertEqual(rows, [])
        self.assertEqual(x_key, "")

    def test_profile_for_blueprint_detects_date_column(self):
        df = pd.DataFrame({"Order Date": ["2024-01-01"], "Sales": [100]})
        profile = profile_for_blueprint(df)
        self.assertEqual(profile["date_column"], "Order Date")
        self.assertIn("Sales", profile["numeric_columns"])


class DatasetPipelineTests(TestCase):
    def test_load_seed_dataset_has_rows(self):
        df = load_seed_dataset()
        self.assertGreater(len(df), 0)

    def test_load_active_dataframe_falls_back_to_seed(self):
        df = load_active_dataframe()
        self.assertGreater(len(df), 0)

    def test_resolve_active_upload_prefers_explicit_upload(self):
        upload = DatasetUpload.objects.create(
            source_type="file",
            stored_path="/nonexistent/path.csv",
            status="processed",
        )
        self.assertEqual(resolve_active_upload(upload), upload)

    def test_active_blueprint_uses_override(self):
        override = {"kpi_columns": ["Sales"]}
        self.assertEqual(active_blueprint(blueprint_override=override), override)


class AnalyticsPayloadTests(TestCase):
    def test_build_analytics_payload_with_default_dataset(self):
        payload = build_analytics_payload()
        self.assertGreater(payload["records"], 0)
        self.assertIn("kpi_cards", payload)
        self.assertIn("charts", payload)
        self.assertEqual(payload["dataset_mode"], "generic")


class ChatSessionScopeTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="alice", password="secret")
        self.other = User.objects.create_user(username="bob", password="secret")

        from analytics_assistant.request_context import resolve_active_workspace
        req_user = type("Req", (), {"user": self.user})()
        req_other = type("Req", (), {"user": self.other})()
        self.ws_user = resolve_active_workspace(req_user)
        self.ws_other = resolve_active_workspace(req_other)

    def test_authenticated_user_cannot_access_foreign_session(self):
        session = ChatSession.objects.create(user=self.other, workspace=self.ws_other, role="ceo", title="Private")
        request = self.factory.get("/")
        request.user = self.user
        self.assertFalse(session_belongs_to_request(session, request))

    def test_anonymous_user_cannot_access_authenticated_session(self):
        session = ChatSession.objects.create(user=self.user, workspace=self.ws_user, role="ceo", title="Private")
        request = self.factory.get("/")
        request.user = AnonymousUser()
        self.assertFalse(session_belongs_to_request(session, request))


class ApiIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)

    def test_health_check(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_analytics_summary_returns_payload(self):
        response = self.client.get("/api/analytics/summary/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("kpi_cards", data)
        self.assertIn("widgets", data)

    def test_chat_requires_message(self):
        response = self.client.post("/api/chat/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.json())

    def test_chat_accepts_valid_message(self):
        response = self.client.post(
            "/api/chat/",
            {"message": "What trends do you see?"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reply", data)
        self.assertIn("session_id", data)

    def test_upload_link_blocks_localhost(self):
        response = self.client.post(
            "/api/data/upload-link/",
            {"url": "http://127.0.0.1/secrets.csv"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_blueprint_get_returns_json(self):
        response = self.client.get("/api/dashboard/blueprint/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("effective_blueprint", response.json())

    def test_upload_requires_file(self):
        response = self.client.post("/api/data/upload/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "No file uploaded.")


class EnvValidationTests(SimpleTestCase):
    def _good_secret(self) -> str:
        return "x" * 50

    def test_development_allows_insecure_defaults(self):
        validate_deployment_env(
            django_env="development",
            debug=True,
            secret_key=INSECURE_DEV_SECRET_KEY,
            allowed_hosts=["*"],
        )

    def test_production_rejects_debug(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_deployment_env(
                django_env="production",
                debug=True,
                secret_key=self._good_secret(),
                allowed_hosts=["example.com"],
            )
        self.assertIn("DEBUG", str(ctx.exception))

    def test_production_rejects_insecure_secret(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_deployment_env(
                django_env="production",
                debug=False,
                secret_key=INSECURE_DEV_SECRET_KEY,
                allowed_hosts=["example.com"],
            )
        self.assertIn("DJANGO_SECRET_KEY", str(ctx.exception))

    def test_production_rejects_wildcard_hosts(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_deployment_env(
                django_env="production",
                debug=False,
                secret_key=self._good_secret(),
                allowed_hosts=["*"],
            )
        self.assertIn("ALLOWED_HOSTS", str(ctx.exception))

    def test_production_accepts_valid_config(self):
        validate_deployment_env(
            django_env="production",
            debug=False,
            secret_key=self._good_secret(),
            allowed_hosts=["example.com"],
        )

    def test_is_insecure_secret_key_detects_placeholders(self):
        self.assertTrue(is_insecure_secret_key("change-me-in-production"))
        self.assertFalse(is_insecure_secret_key("a" * 50))


# ---------------------------------------------------------------------------
# Phase 1.5 New Tests
# ---------------------------------------------------------------------------

class SsrfRedirectTests(SimpleTestCase):
    """Verify the redirect hook in build_safe_session blocks private destinations."""

    def test_redirect_hook_blocks_private_ip_destination(self):
        """The _redirect_hook should raise ValueError for private-IP redirect targets."""
        from unittest.mock import MagicMock
        from analytics_assistant.url_safety import _redirect_hook

        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.headers = {"Location": "http://192.168.1.1/evil.csv"}

        with self.assertRaises(ValueError) as ctx:
            _redirect_hook(mock_response)
        self.assertIn("SSRF redirect protection", str(ctx.exception))

    def test_redirect_hook_allows_public_destination(self):
        """The _redirect_hook should not raise for public-IP redirect targets."""
        import socket
        from unittest.mock import MagicMock, patch
        from analytics_assistant.url_safety import _redirect_hook

        mock_response = MagicMock()
        mock_response.is_redirect = True
        mock_response.headers = {"Location": "https://example.com/data.csv"}

        def _public_resolver(hostname, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]

        with patch("analytics_assistant.url_safety.socket.getaddrinfo", _public_resolver):
            # Should not raise
            _redirect_hook(mock_response)

    def test_redirect_hook_passes_non_redirect(self):
        """Non-redirect responses should pass through the hook unchanged."""
        from unittest.mock import MagicMock
        from analytics_assistant.url_safety import _redirect_hook

        mock_response = MagicMock()
        mock_response.is_redirect = False
        # No exception expected
        _redirect_hook(mock_response)

    def test_build_safe_session_returns_session_with_hook(self):
        """build_safe_session() should return a Session with our redirect hook registered."""
        from analytics_assistant.url_safety import _redirect_hook, build_safe_session
        session = build_safe_session()
        self.assertIn(_redirect_hook, session.hooks["response"])


class UploadValidationTests(SimpleTestCase):
    """Verify upload_service rejects oversized files and disallowed types."""

    def test_validate_upload_size_rejects_oversized(self):
        from analytics_assistant.upload_service import _validate_upload_size
        with self.assertRaises(ValueError) as ctx:
            _validate_upload_size(30 * 1024 * 1024, label="File")
        self.assertIn("exceeds the maximum", str(ctx.exception))

    def test_validate_upload_size_allows_small_file(self):
        from analytics_assistant.upload_service import _validate_upload_size
        # Should not raise
        _validate_upload_size(1024)

    def test_validate_mime_type_rejects_executable(self):
        """MIME validation should reject a .exe file (application/x-msdownload or similar)."""
        from pathlib import Path
        from unittest.mock import patch
        from analytics_assistant.upload_service import _validate_mime_type
        with patch("mimetypes.guess_type", return_value=("application/x-msdownload", None)):
            with self.assertRaises(ValueError) as ctx:
                _validate_mime_type(Path("malware.exe"))
            self.assertIn("not allowed", str(ctx.exception))

    def test_validate_mime_type_allows_csv(self):
        from pathlib import Path
        from analytics_assistant.upload_service import _validate_mime_type
        # Should not raise for .csv
        _validate_mime_type(Path("data.csv"))

    def test_validate_mime_type_allows_xlsx(self):
        from pathlib import Path
        from analytics_assistant.upload_service import _validate_mime_type
        # Should not raise for .xlsx
        _validate_mime_type(Path("report.xlsx"))


class AnonymousSessionIsolationTests(TestCase):
    """Verify anonymous ChatSessions are bound to browser session key (TD-003 fix)."""

    def test_anonymous_session_belongs_to_same_session_key(self):
        """A session with matching session_key should belong to the request."""
        session = ChatSession.objects.create(
            user=None, session_key="abc123", role="team_member", title="Test"
        )
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.session = type("S", (), {"session_key": "abc123"})()
        self.assertTrue(session_belongs_to_request(session, request))

    def test_anonymous_session_does_not_belong_to_different_session_key(self):
        """A session with a different session_key should NOT belong to the request."""
        session = ChatSession.objects.create(
            user=None, session_key="abc123", role="team_member", title="Test"
        )
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.session = type("S", (), {"session_key": "xyz789"})()
        self.assertFalse(session_belongs_to_request(session, request))

    def test_session_without_session_attr_returns_false(self):
        """RequestFactory requests (no session middleware) should not match any stored session."""
        session = ChatSession.objects.create(
            user=None, session_key="abc123", role="team_member", title="Test"
        )
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        # No session attribute — simulates RequestFactory
        self.assertFalse(session_belongs_to_request(session, request))

    def test_chatsession_has_session_key_field(self):
        """ChatSession model must have session_key field (migration guard)."""
        session = ChatSession.objects.create(
            user=None, session_key="test-key-001", role="ceo", title="Isolation Test"
        )
        reloaded = ChatSession.objects.get(pk=session.pk)
        self.assertEqual(reloaded.session_key, "test-key-001")


class HealthCheckTests(TestCase):
    """Verify health check returns correct structure and status codes."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()

    def test_health_check_returns_200_with_ok_status(self):
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_health_check_returns_version(self):
        response = self.client.get("/health/")
        data = response.json()
        self.assertIn("version", data)
        self.assertEqual(data["version"], "0.7.0")

    def test_health_check_includes_database_check(self):
        response = self.client.get("/health/")
        data = response.json()
        self.assertIn("checks", data)
        self.assertIn("database", data["checks"])
        self.assertEqual(data["checks"]["database"], "ok")


class BlueprintSaveTests(TestCase):
    """Verify blueprint save/load round-trip (regression coverage for TD-018)."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient(enforce_csrf_checks=False)

    def test_blueprint_post_saves_override(self):
        payload = {"blueprint": {"kpi_columns": ["revenue"], "trend_metric": "revenue"}}
        response = self.client.post("/api/dashboard/blueprint/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["detail"], "Blueprint saved.")

    def test_blueprint_get_returns_saved_override(self):
        payload = {"blueprint": {"kpi_columns": ["orders"]}}
        self.client.post("/api/dashboard/blueprint/", payload, format="json")
        response = self.client.get("/api/dashboard/blueprint/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["effective_blueprint"].get("kpi_columns"), ["orders"])


class UploadApiTests(TestCase):
    """API-level file upload tests (E2E with fixture CSV)."""

    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient(enforce_csrf_checks=False)

    def test_upload_rejects_disallowed_extension(self):
        import io
        fake_file = io.BytesIO(b"fake content")
        fake_file.name = "malware.exe"
        response = self.client.post(
            "/api/data/upload/",
            {"file": fake_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.json())

    def test_upload_accepts_valid_csv(self):
        import io
        csv_content = b"date,revenue,orders\n2024-01-01,1000,10\n2024-01-02,1500,15\n"
        fake_file = io.BytesIO(csv_content)
        fake_file.name = "test_data.csv"
        fake_file.size = len(csv_content)
        response = self.client.post(
            "/api/data/upload/",
            {"file": fake_file},
            format="multipart",
        )
        # Should succeed (200) or fail with schema error (400) — not a 500.
        self.assertIn(response.status_code, [200, 400])
        if response.status_code == 400:
            self.assertIn("detail", response.json())


class DatasetManagementTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=False)
        self.user_a = User.objects.create_user(username="usera", password="password")
        self.user_b = User.objects.create_user(username="userb", password="password")
        
        from analytics_assistant.request_context import resolve_active_workspace
        req_a = type("Req", (), {"user": self.user_a})()
        req_b = type("Req", (), {"user": self.user_b})()
        self.ws_a = resolve_active_workspace(req_a)
        self.ws_b = resolve_active_workspace(req_b)

        # Datasets for User A
        self.dataset_a = DatasetUpload.objects.create(
            workspace=self.ws_a,
            owner=self.user_a,
            name="dataset_a.csv",
            source_type="file",
            stored_path="datasets/dataset_a.csv",
            row_count=10,
            status="processed",
        )
        # Datasets for User B
        self.dataset_b = DatasetUpload.objects.create(
            workspace=self.ws_b,
            owner=self.user_b,
            name="dataset_b.csv",
            source_type="file",
            stored_path="datasets/dataset_b.csv",
            row_count=20,
            status="processed",
        )

    def test_list_datasets_authenticated_user_a(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get("/api/data/datasets/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.dataset_a.id)

    def test_list_datasets_authenticated_user_b(self):
        self.client.force_authenticate(user=self.user_b)
        response = self.client.get("/api/data/datasets/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["id"], self.dataset_b.id)

    def test_list_datasets_anonymous_session_isolation(self):
        # First session
        session_a = self.client.session
        session_a["foo"] = "bar"
        session_a.save()
        key_a = session_a.session_key

        ds_anon_a = DatasetUpload.objects.create(
            session_key=key_a,
            name="anon_a.csv",
            source_type="file",
            stored_path="datasets/anon_a.csv",
            row_count=5,
            status="processed",
        )

        response = self.client.get("/api/data/datasets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], ds_anon_a.id)

        # Switch to second session
        self.client.logout()
        session_b = self.client.session
        session_b["foo"] = "baz"
        session_b.save()
        key_b = session_b.session_key

        response = self.client.get("/api/data/datasets/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)  # Empty for session B

    def test_cannot_activate_foreign_dataset(self):
        self.client.force_authenticate(user=self.user_a)
        # Attempt to activate B's dataset
        response = self.client.post(f"/api/data/datasets/{self.dataset_b.id}/activate/")
        self.assertEqual(response.status_code, 404)

    def test_cannot_rename_foreign_dataset(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.patch(
            f"/api/data/datasets/{self.dataset_b.id}/",
            {"name": "hacked.csv"},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_archive_foreign_dataset(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(f"/api/data/datasets/{self.dataset_b.id}/archive/")
        self.assertEqual(response.status_code, 404)

    def test_cannot_delete_foreign_dataset(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.delete(f"/api/data/datasets/{self.dataset_b.id}/")
        self.assertEqual(response.status_code, 404)

    def test_activate_dataset_success(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.post(f"/api/data/datasets/{self.dataset_a.id}/activate/")
        self.assertEqual(response.status_code, 200)
        
        # Verify state is updated
        from analytics_assistant.request_context import resolve_dashboard_state
        request = type("R", (), {"user": self.user_a})()
        state = resolve_dashboard_state(request)
        self.assertEqual(state.active_upload, self.dataset_a)

    def test_deactivate_dataset_reverts_to_seed(self):
        self.client.force_authenticate(user=self.user_a)
        # First activate
        self.client.post(f"/api/data/datasets/{self.dataset_a.id}/activate/")
        # Now deactivate
        response = self.client.post("/api/data/datasets/deactivate/")
        self.assertEqual(response.status_code, 200)
        
        # Verify active dataset is None
        request = type("R", (), {"user": self.user_a})()
        from analytics_assistant.request_context import resolve_dashboard_state
        state = resolve_dashboard_state(request)
        self.assertIsNone(state.active_upload)

    def test_rename_dataset_success(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.patch(
            f"/api/data/datasets/{self.dataset_a.id}/",
            {"name": "new_name.csv", "description": "some description"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.dataset_a.refresh_from_db()
        self.assertEqual(self.dataset_a.name, "new_name.csv")
        self.assertEqual(self.dataset_a.description, "some description")

    def test_archive_dataset_success(self):
        self.client.force_authenticate(user=self.user_a)
        self.assertFalse(self.dataset_a.is_archived)
        response = self.client.post(f"/api/data/datasets/{self.dataset_a.id}/archive/")
        self.assertEqual(response.status_code, 200)
        self.dataset_a.refresh_from_db()
        self.assertTrue(self.dataset_a.is_archived)

    def test_delete_dataset_success(self):
        self.client.force_authenticate(user=self.user_a)
        # Activate it first
        self.client.post(f"/api/data/datasets/{self.dataset_a.id}/activate/")
        
        # Make a mock stored file path
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"data")
            temp_path = f.name
            
        self.dataset_a.stored_path = temp_path
        self.dataset_a.save()
        
        # Delete
        response = self.client.delete(f"/api/data/datasets/{self.dataset_a.id}/")
        self.assertEqual(response.status_code, 200)
        
        # Verify db record deleted
        self.assertFalse(DatasetUpload.objects.filter(pk=self.dataset_a.id).exists())
        
        # Verify file deleted
        self.assertFalse(os.path.exists(temp_path))
        
        # Verify active dataset is reset to None
        request = type("R", (), {"user": self.user_a})()
        from analytics_assistant.request_context import resolve_dashboard_state
        state = resolve_dashboard_state(request)
        self.assertIsNone(state.active_upload)

    def test_cannot_activate_archived_dataset(self):
        self.client.force_authenticate(user=self.user_a)
        self.dataset_a.is_archived = True
        self.dataset_a.save(update_fields=["is_archived"])
        response = self.client.post(f"/api/data/datasets/{self.dataset_a.id}/activate/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Archived", response.json()["detail"])

    def test_list_versions(self):
        self.client.force_authenticate(user=self.user_a)
        version = DatasetVersion.objects.create(
            dataset=self.dataset_a,
            version_number=1,
            name="v1.csv",
            source_type="file",
            row_count=10,
        )
        response = self.client.get(f"/api/data/datasets/{self.dataset_a.id}/versions/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["version_number"], 1)

    def test_cannot_list_foreign_versions(self):
        self.client.force_authenticate(user=self.user_a)
        response = self.client.get(f"/api/data/datasets/{self.dataset_b.id}/versions/")
        self.assertEqual(response.status_code, 404)

    def test_upload_new_version_success(self):
        self.client.force_authenticate(user=self.user_a)
        import io
        csv_content = b"date,revenue,orders\n2024-01-01,1000,10\n2024-01-02,1500,15\n"
        fake_file = io.BytesIO(csv_content)
        fake_file.name = "v2.csv"
        fake_file.size = len(csv_content)

        # Ensure initial version exists so version number bumps correctly
        DatasetVersion.objects.create(
            dataset=self.dataset_a,
            version_number=1,
            name=self.dataset_a.name,
            source_type=self.dataset_a.source_type,
            row_count=self.dataset_a.row_count,
        )

        response = self.client.post(
            f"/api/data/datasets/{self.dataset_a.id}/versions/upload/",
            {"file": fake_file},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        self.dataset_a.refresh_from_db()
        self.assertEqual(self.dataset_a.active_version_number, 2)
        self.assertEqual(self.dataset_a.versions.count(), 2)

    def test_restore_version(self):
        self.client.force_authenticate(user=self.user_a)
        v1 = DatasetVersion.objects.create(
            dataset=self.dataset_a,
            version_number=1,
            name="v1.csv",
            source_type="file",
            row_count=10,
            stored_path="datasets/v1.csv",
        )
        v2 = DatasetVersion.objects.create(
            dataset=self.dataset_a,
            version_number=2,
            name="v2.csv",
            source_type="file",
            row_count=20,
            stored_path="datasets/v2.csv",
        )
        response = self.client.post(f"/api/data/datasets/{self.dataset_a.id}/versions/1/restore/")
        self.assertEqual(response.status_code, 200)
        self.dataset_a.refresh_from_db()
        self.assertEqual(self.dataset_a.active_version_number, 1)
        self.assertEqual(self.dataset_a.row_count, 10)

    def test_compare_versions(self):
        self.client.force_authenticate(user=self.user_a)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f1:
            f1.write("date,revenue,orders\n2024-01-01,1000,10\n2024-01-02,1100,12\n")
            path1 = f1.name
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f2:
            f2.write("date,revenue,orders,extra\n2024-01-01,1200,15,abc\n2024-01-02,1400,20,xyz\n")
            path2 = f2.name

        try:
            v1 = DatasetVersion.objects.create(
                dataset=self.dataset_a,
                version_number=1,
                name="v1.csv",
                source_type="file",
                row_count=2,
                stored_path=path1,
            )
            v2 = DatasetVersion.objects.create(
                dataset=self.dataset_a,
                version_number=2,
                name="v2.csv",
                source_type="file",
                row_count=2,
                stored_path=path2,
            )
            
            response = self.client.get(
                f"/api/data/datasets/{self.dataset_a.id}/versions/compare/?v1=1&v2=2"
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["row_count_diff"], 0)
            self.assertIn("extra", data["columns_diff"]["added"])
            self.assertEqual(data["numeric_stats_compare"]["revenue"]["mean_diff"], 250.0)
        finally:
            import os
            try:
                os.remove(path1)
                os.remove(path2)
            except Exception:
                pass


class WorkspaceTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user_a = User.objects.create_user(username="usera", password="password")
        self.user_b = User.objects.create_user(username="userb", password="password")
        
        # Resolve active workspaces to trigger auto-creation
        from analytics_assistant.request_context import resolve_active_workspace
        request_a = type("Req", (), {"user": self.user_a})()
        request_b = type("Req", (), {"user": self.user_b})()
        
        self.ws_a = resolve_active_workspace(request_a)
        self.ws_b = resolve_active_workspace(request_b)

    def test_default_workspace_created(self):
        self.assertIsNotNone(self.ws_a)
        self.assertEqual(self.ws_a.owner, self.user_a)
        self.assertEqual(self.ws_a.name, "usera's Workspace")

    def test_dataset_scoping_to_workspace(self):
        # Create dataset in workspace A
        ds_a = DatasetUpload.objects.create(
            workspace=self.ws_a,
            owner=self.user_a,
            source_type="file",
            name="dataset_a.csv",
        )
        # Create dataset in workspace B
        ds_b = DatasetUpload.objects.create(
            workspace=self.ws_b,
            owner=self.user_b,
            source_type="file",
            name="dataset_b.csv",
        )

        from analytics_assistant.request_context import user_dataset_queryset
        
        # Check queryset for user A
        request_a = type("Req", (), {"user": self.user_a})()
        qs_a = user_dataset_queryset(request_a)
        self.assertIn(ds_a, qs_a)
        self.assertNotIn(ds_b, qs_a)

        # Check queryset for user B
        request_b = type("Req", (), {"user": self.user_b})()
        qs_b = user_dataset_queryset(request_b)
        self.assertIn(ds_b, qs_b)
        self.assertNotIn(ds_a, qs_b)

    def test_anonymous_session_isolation(self):
        from django.contrib.auth.models import AnonymousUser
        class DummySession:
            def __init__(self):
                self.session_key = "anon_key_1"
            def save(self):
                pass
        request = type("Req", (), {
            "user": AnonymousUser(),
            "session": DummySession()
        })()
        
        from analytics_assistant.request_context import resolve_dashboard_state
        state = resolve_dashboard_state(request)
        self.assertIsNone(state.workspace)
        self.assertEqual(state.session_key, "anon_key_1")


class AuthenticationTests(TestCase):
    def test_register_creates_user_profile_and_workspace(self):
        response = self.client.post(
            "/register/",
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "StrongPass123_!",
                "password2": "StrongPass123_!",
            },
        )
        self.assertEqual(response.status_code, 302)  # Redirects to dashboard

        # Verify database structures
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(username="newuser")
        self.assertEqual(user.email, "newuser@example.com")

        # Verify workspace is created
        self.assertEqual(user.workspaces.count(), 1)
        self.assertEqual(user.workspaces.first().name, "newuser's Workspace")

        # Verify profile is created
        self.assertIsNotNone(user.profile)
        self.assertEqual(user.profile.timezone, "UTC")

    def test_login_remember_me(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create_user(username="testlogin", password="StrongPass123_!")

        # Test with remember_me
        response = self.client.post(
            "/login/",
            {"username": "testlogin", "password": "StrongPass123_!", "remember_me": "true"},
        )
        self.assertEqual(response.status_code, 302)
        # 2 weeks expiry (1209600 seconds)
        self.assertEqual(self.client.session.get_expiry_age(), 1209600)
        self.assertFalse(self.client.session.get_expire_at_browser_close())

        # Test without remember_me
        self.client.logout()
        response = self.client.post(
            "/login/",
            {"username": "testlogin", "password": "StrongPass123_!"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_anonymous_datasets_claimed_on_login(self):
        self.client.get("/")
        anon_session_key = self.client.session.session_key
        self.assertTrue(anon_session_key)

        dataset = DatasetUpload.objects.create(
            session_key=anon_session_key,
            source_type="file",
            name="anon_data.csv",
            status="processed",
        )

        from django.contrib.auth import get_user_model
        User = get_user_model()
        User.objects.create_user(username="testclaim", password="StrongPass123_!")

        response = self.client.post(
            "/login/",
            {"username": "testclaim", "password": "StrongPass123_!"},
        )
        self.assertEqual(response.status_code, 302)

        dataset.refresh_from_db()
        self.assertIsNotNone(dataset.workspace)
        self.assertEqual(dataset.owner.username, "testclaim")


class UserProfileAndSettingsTests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient
        self.client = APIClient()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="settingsuser", password="StrongPass123_!", email="settings@example.com")
        
        # Pre-provision default workspace
        from analytics_assistant.request_context import resolve_active_workspace
        dummy_req = type("Req", (), {"user": self.user})()
        resolve_active_workspace(dummy_req)
        
        self.client.force_authenticate(user=self.user)

    def test_update_profile(self):
        response = self.client.post(
            "/api/profile/update/",
            {
                "display_name": "Settings User Display",
                "bio": "Bio content here",
                "timezone": "Europe/London",
                "email": "newsettings@example.com",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["display_name"], "Settings User Display")
        self.assertEqual(data["email"], "newsettings@example.com")
        
        # Verify db profile
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.display_name, "Settings User Display")
        self.assertEqual(self.user.profile.bio, "Bio content here")
        self.assertEqual(self.user.profile.timezone, "Europe/London")
        self.assertEqual(self.user.email, "newsettings@example.com")

    def test_update_settings(self):
        response = self.client.post(
            "/api/settings/update/",
            {"theme_preference": "light"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["theme_preference"], "light")
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.theme_preference, "light")

    def test_export_account_data(self):
        response = self.client.get("/api/settings/export-data/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user"]["username"], "settingsuser")
        self.assertIn("workspaces", data)

    def test_delete_account(self):
        response = self.client.post("/api/settings/delete-account/")
        self.assertEqual(response.status_code, 200)
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.assertFalse(User.objects.filter(username="settingsuser").exists())


from unittest.mock import MagicMock, patch
from analytics_assistant.crypto import encrypt_password, decrypt_password

class CryptographyTests(TestCase):
    def test_encrypt_decrypt(self):
        plain = "SuperSecretDbPassword123!"
        enc = encrypt_password(plain)
        self.assertNotEqual(plain, enc)
        self.assertEqual(plain, decrypt_password(enc))


class ConnectorPipelineTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="dbuser", password="StrongPass123_!")
        from analytics_assistant.request_context import resolve_active_workspace
        dummy_req = type("Req", (), {"user": self.user})()
        self.workspace = resolve_active_workspace(dummy_req)

    @patch("analytics_assistant.connectors.postgres.PostgresConnector._get_connection")
    def test_test_postgres_connection_success(self, mock_get_conn):
        from analytics_assistant.connector_pipeline import test_connection
        mock_conn = MagicMock()
        mock_get_conn.return_value = mock_conn

        config = {
            "host": "localhost",
            "port": 5432,
            "username": "postgres",
            "password": encrypt_password("pass"),
            "database": "testdb",
        }
        success, msg = test_connection("postgres", config)
        self.assertTrue(success)
        mock_get_conn.assert_called_once_with(config)
        mock_conn.close.assert_called_once()

    @patch("analytics_assistant.connectors.postgres.PostgresConnector._get_connection")
    def test_discover_postgres_tables(self, mock_get_conn):
        from analytics_assistant.connector_pipeline import discover_tables
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [("users",), ("sales_data",)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        config = {
            "host": "localhost",
            "port": 5432,
            "username": "postgres",
            "password": encrypt_password("pass"),
            "database": "testdb",
        }
        tables = discover_tables("postgres", config)
        self.assertEqual(tables, ["users", "sales_data"])
        mock_get_conn.assert_called_once_with(config)

    @patch("analytics_assistant.connectors.postgres.PostgresConnector._get_connection")
    def test_fetch_postgres_table_data(self, mock_get_conn):
        from analytics_assistant.connector_pipeline import fetch_table_data
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.description = [("date",), ("revenue",), ("orders",), ("ad_spend",), ("conversion_rate",), ("channel",)]
        mock_cur.fetchall.return_value = [
            ("2026-01-01", 100.0, 5, 20.0, 0.05, "google"),
            ("2026-01-02", 200.0, 10, 40.0, 0.06, "facebook"),
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        config = {
            "host": "localhost",
            "port": 5432,
            "username": "postgres",
            "password": encrypt_password("pass"),
            "database": "testdb",
        }
        df = fetch_table_data("postgres", config, "sales_data")
        self.assertEqual(df.shape, (2, 6))
        self.assertEqual(list(df.columns), ["date", "revenue", "orders", "ad_spend", "conversion_rate", "channel"])
        mock_get_conn.assert_called_once_with(config)

    @patch("analytics_assistant.connectors.postgres.PostgresConnector._get_connection")
    def test_sync_dataset_postgres_increments_version(self, mock_get_conn):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.description = [("date",), ("revenue",), ("orders",), ("ad_spend",), ("conversion_rate",), ("channel",)]
        mock_cur.fetchall.return_value = [
            ("2026-01-01", 100.0, 5, 20.0, 0.05, "google"),
            ("2026-01-02", 200.0, 10, 40.0, 0.06, "facebook"),
        ]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_get_conn.return_value = mock_conn

        dataset = DatasetUpload.objects.create(
            workspace=self.workspace,
            owner=self.user,
            name="Db Sync Dataset",
            source_type="postgres",
            connection_config={
                "host": "localhost",
                "port": 5432,
                "username": "postgres",
                "password": encrypt_password("pass"),
                "database": "testdb",
                "table": "sales_data",
            },
            active_version_number=1,
            status="processed"
        )
        DatasetVersion.objects.create(
            dataset=dataset,
            version_number=1,
            source_type="postgres",
            row_count=2,
        )

        dummy_req = type("Req", (), {"user": self.user})()
        from analytics_assistant.connector_pipeline import sync_dataset_source
        res = sync_dataset_source(dummy_req, dataset)

        self.assertEqual(res["version_number"], 2)
        dataset.refresh_from_db()
        self.assertEqual(dataset.active_version_number, 2)
        self.assertEqual(dataset.versions.count(), 2)


class AjaxAuthenticationTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="ajaxuser", password="StrongPassword123_!")

    def test_api_login_success(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "ajaxuser", "password": "StrongPassword123_!", "remember_me": True},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        # Verify user is logged in
        self.assertTrue(int(self.client.session["_auth_user_id"]) == self.user.id)
        # Expiry is set (2 weeks)
        self.assertEqual(self.client.session.get_expiry_age(), 1209600)

    def test_api_login_invalid_credentials(self):
        response = self.client.post(
            "/api/auth/login/",
            {"username": "ajaxuser", "password": "WrongPassword!"},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"], "Invalid username or password.")

    def test_api_register_success(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "ajaxnewuser",
                "email": "ajaxnewuser@example.com",
                "password1": "NewStrongPass123_!",
                "password2": "NewStrongPass123_!",
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["success"])

        from django.contrib.auth import get_user_model
        User = get_user_model()
        new_user = User.objects.get(username="ajaxnewuser")
        self.assertEqual(new_user.email, "ajaxnewuser@example.com")
        self.assertEqual(new_user.workspaces.count(), 1)
        self.assertIsNotNone(new_user.profile)

    def test_api_register_validation_errors(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "ajaxuser",  # Already exists
                "email": "invalidemail",
                "password1": "short",
                "password2": "mismatch",
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)


class IntelligentAnalyticsTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.user = User.objects.create_user(username="analyst_user", password="StrongPassword123_!")
        self.client.force_login(self.user)
        
        # Create active workspace and user profile
        from analytics_assistant.models import Workspace, DatasetUpload, DatasetVersion
        self.workspace = Workspace.objects.create(name="analyst_user's Workspace", owner=self.user)

        self.dataset = DatasetUpload.objects.create(
            name="Anomaly Data",
            owner=self.user,
            workspace=self.workspace,
            source_type="file",
            row_count=10,
        )
        self.version = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number=1,
            source_type="file",
            row_count=10,
        )
        self.version2 = DatasetVersion.objects.create(
            dataset=self.dataset,
            version_number=2,
            source_type="file",
            row_count=10,
        )

    def test_run_intelligent_analytics_calculations(self):
        import pandas as pd
        from analytics_assistant.intelligent_analytics import run_intelligent_analytics
        
        # Build 15 points to prevent outlier masking
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=15),
            "revenue": [100.0, 102.0, 98.0, 101.0, 100.0, 99.0, 9999.0, 101.0, 100.0, 99.0, 100.0, 102.0, 98.0, 101.0, 100.0],
            "channel": ["Meta"] * 15
        })
        
        res = run_intelligent_analytics(df, "Test Table", "file")
        
        self.assertIn("anomalies", res)
        self.assertIn("trends", res)
        self.assertIn("contributors", res)
        self.assertIn("narratives", res)
        
        anom_types = [a["type"] for a in res["anomalies"]]
        self.assertIn("outliers", anom_types)
        
        # Verify the new keys exist on anomalies
        for a in res["anomalies"]:
            self.assertIn("severity", a)
            self.assertIn("business_impact", a)
            self.assertIn("why_happened", a)
            
        # Verify severity sorting (critical -> high -> medium -> low)
        weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        prev_weight = 5
        for a in res["anomalies"]:
            curr_weight = weights.get(a["severity"], 1)
            self.assertTrue(curr_weight <= prev_weight, f"Anomalies not ranked correctly by severity: {curr_weight} > {prev_weight}")
            prev_weight = curr_weight

    def test_insights_caching_on_version(self):
        self.assertEqual(self.version.insights_cache, {})
        
        import pandas as pd
        from unittest.mock import patch
        
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=5),
            "revenue": [10.0, 12.0, 11.0, 14.0, 15.0],
            "channel": ["A", "B", "A", "B", "A"]
        })
        
        with patch("analytics_assistant.views.resolve_dashboard_state") as mock_state:
            mock_state.return_value = type("State", (), {
                "active_upload": self.dataset,
                "blueprint_override": None
            })
            with patch("analytics_assistant.dataset_pipeline.load_active_dataframe", return_value=df):
                response = self.client.get("/api/analytics/summary/")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn("proactive_insights", data)
                
                self.version.refresh_from_db()
                self.assertIsNotNone(self.version.insights_cache)
                self.assertEqual(self.version.insights_cache["confidence_score"], 1.0)

    def test_compare_version_insights_view(self):
        self.version.insights_cache = {"narratives": {"executive_summary": "Version 1 Summary"}}
        self.version.save()
        self.version2.insights_cache = {"narratives": {"executive_summary": "Version 2 Summary"}}
        self.version2.save()
        
        response = self.client.get(
            f"/api/data/datasets/{self.dataset.pk}/versions/compare_insights/?v1=1&v2=2"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["v1"]["narratives"]["executive_summary"], "Version 1 Summary")
        self.assertEqual(data["v2"]["narratives"]["executive_summary"], "Version 2 Summary")

    def test_schema_change_detection(self):
        import pandas as pd
        from analytics_assistant.intelligent_analytics import run_intelligent_analytics
        
        dataset = DatasetUpload.objects.create(
            name="Schema Test Dataset",
            source_type="file",
            active_version_number=2,
        )
        v1 = DatasetVersion.objects.create(
            dataset=dataset,
            version_number=1,
            source_type="file",
            ai_blueprint={"columns": [{"name": "date", "type": "datetime"}, {"name": "revenue", "type": "numeric"}]}
        )
        df_v2 = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=5),
            "revenue": [10.0, 12.0, 11.0, 14.0, 15.0],
            "new_column": ["A", "B", "A", "B", "A"]
        })
        
        res = run_intelligent_analytics(df_v2, "Schema Test Dataset", "file", dataset_upload=dataset)
        anoms = res.get("anomalies", [])
        schema_anom = [a for a in anoms if a["type"] == "schema_change"]
        self.assertTrue(len(schema_anom) > 0)
        self.assertIn("Schema modified since version 1", schema_anom[0]["message"])
        self.assertEqual(schema_anom[0]["confidence"], 1.0)
        self.assertIn("what_happened", schema_anom[0])
        self.assertIn("why_happened", schema_anom[0])

    def test_category_shift_detection(self):
        import pandas as pd
        from analytics_assistant.intelligent_analytics import run_intelligent_analytics
        
        channels = ["A"] * 15 + ["B"] * 13 + ["C"] * 2
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=30),
            "revenue": [10.0] * 30,
            "channel": channels
        })
        res = run_intelligent_analytics(df, "Category Test", "file")
        anoms = res.get("anomalies", [])
        shifts = [a for a in anoms if a["type"] == "category_shift"]
        self.assertTrue(len(shifts) > 0)
        self.assertIn("shifted", shifts[0]["message"])

    def test_trend_reversal_and_seasonality(self):
        import pandas as pd
        from analytics_assistant.intelligent_analytics import run_intelligent_analytics
        
        revenue = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 20, 18, 16, 14, 12]
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=15),
            "revenue": revenue,
            "channel": ["Meta"] * 15
        })
        res = run_intelligent_analytics(df, "Trend Test", "file")
        highlights = res.get("business_highlights", [])
        reversal_highlights = [h for h in highlights if "Trend Reversal" in h]
        self.assertTrue(len(reversal_highlights) > 0)
        
        dates = pd.date_range("2026-07-01", periods=28)
        revs = []
        for d in dates:
            if d.dayofweek >= 5:
                revs.append(10.0)
            else:
                revs.append(100.0)
        df_season = pd.DataFrame({
            "date": dates,
            "revenue": revs,
            "channel": ["Meta"] * 28
        })
        res_season = run_intelligent_analytics(df_season, "Seasonality Test", "file")
        highlights_season = res_season.get("business_highlights", [])
        season_hl = [h for h in highlights_season if "seasonality" in h.lower()]
        self.assertTrue(len(season_hl) > 0)

    def test_root_cause_analysis(self):
        import pandas as pd
        from analytics_assistant.intelligent_analytics import run_intelligent_analytics
        
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=6),
            "revenue": [5, 5, 5, 5, 25, 25],
            "channel": ["A", "B", "A", "B", "A", "B"]
        })
        res = run_intelligent_analytics(df, "Root Cause Test", "file")
        contribs = res.get("contributors", [])
        self.assertTrue(len(contribs) > 0)
        self.assertEqual(contribs[0]["category"], "B")
        self.assertTrue(contribs[0]["share_pct"] > 50)

    def test_recommendations_and_questions_format(self):
        import pandas as pd
        from analytics_assistant.intelligent_analytics import run_intelligent_analytics
        
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=10),
            "revenue": [10.0] * 10,
            "channel": ["Meta"] * 10
        })
        res = run_intelligent_analytics(df, "Recs Test", "file")
        narratives = res.get("narratives", {})
        recs = narratives.get("recommendations", [])
        questions = narratives.get("suggested_questions", [])
        
        self.assertEqual(len(recs), 5)
        self.assertEqual(len(questions), 5)
        
        for r in recs:
            self.assertIn("Fact:", r)
            self.assertIn("Recommendation:", r)
            self.assertIn("Speculation:", r)

    def test_contradiction_resolution(self):
        import pandas as pd
        from analytics_assistant.intelligent_analytics import run_intelligent_analytics
        
        # Test case: flat overall trend (net change is zero), but has sequential spikes and drops
        df = pd.DataFrame({
            "date": pd.date_range("2026-07-01", periods=5),
            "revenue": [10.0, 15.0, 8.0, 12.0, 10.0],
            "channel": ["Meta"] * 5
        })
        res = run_intelligent_analytics(df, "Contradiction Test", "file")
        anoms = res.get("anomalies", [])
        flat_anom = next((a for a in anoms if a["type"] == "flat"), None)
        self.assertIsNotNone(flat_anom)
        # Should note high daily volatility in the flat trend description
        self.assertIn("sequential daily volatility", flat_anom["message"])
        self.assertIn("cancelled each other out", flat_anom["why_happened"])








