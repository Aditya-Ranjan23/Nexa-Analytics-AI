from django.contrib.auth.models import AnonymousUser, User
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
from analytics_assistant.url_safety import validate_public_http_url


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

    def test_allows_public_https_url(self):
        self.assertEqual(
            validate_public_http_url("https://example.com/data.csv"),
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
