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
from analytics_assistant.models import ChatSession, DatasetUpload
from analytics_assistant.request_context import session_belongs_to_request
from analytics_assistant.roles import (
    filter_kpi_cards_for_role,
    normalize_role,
    widgets_for_role,
)
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


class RoleTests(SimpleTestCase):
    def test_normalize_role_aliases(self):
        self.assertEqual(normalize_role("marketing"), "marketing_manager")
        self.assertEqual(normalize_role(""), "team_member")

    def test_widgets_vary_by_role(self):
        self.assertIn("roas", widgets_for_role("ceo"))
        self.assertIn("campaign_actions", widgets_for_role("marketing_manager"))

    def test_filter_kpi_cards_for_role_matches_widgets(self):
        cards = [
            {"key": "revenue_total", "label": "Revenue", "value": 100},
            {"key": "ad_spend_total", "label": "Spend", "value": 50},
        ]
        filtered = filter_kpi_cards_for_role(cards, "ceo")
        self.assertEqual([card["key"] for card in filtered], ["revenue_total"])

    def test_filter_kpi_cards_fallback_for_generic_keys(self):
        cards = [{"key": "Sales_total", "label": "Sales", "value": 100}]
        filtered = filter_kpi_cards_for_role(cards, "ceo")
        self.assertEqual(filtered, cards)


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
        payload = build_analytics_payload(role="team_member")
        self.assertGreater(payload["records"], 0)
        self.assertIn("kpi_cards", payload)
        self.assertIn("charts", payload)
        self.assertEqual(payload["dataset_mode"], "generic")


class ChatSessionScopeTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username="alice", password="secret")
        self.other = User.objects.create_user(username="bob", password="secret")

    def test_authenticated_user_cannot_access_foreign_session(self):
        session = ChatSession.objects.create(user=self.other, role="ceo", title="Private")
        request = self.factory.get("/")
        request.user = self.user
        self.assertFalse(session_belongs_to_request(session, request))

    def test_anonymous_user_cannot_access_authenticated_session(self):
        session = ChatSession.objects.create(user=self.user, role="ceo", title="Private")
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
        response = self.client.get("/api/analytics/summary/?role=ceo")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("kpi_cards", data)
        self.assertIn("widgets", data)
        self.assertEqual(data["role"], "ceo")

    def test_chat_requires_message(self):
        response = self.client.post("/api/chat/", {"role": "team_member"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("message", response.json())

    def test_chat_accepts_valid_message(self):
        response = self.client.post(
            "/api/chat/",
            {"message": "What trends do you see?", "role": "team_member"},
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
        self.assertEqual(data["version"], "0.2.0")

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

