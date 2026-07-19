from unittest.mock import patch, MagicMock
from django.test import TestCase

from analytics_assistant.connectors.registry import ConnectorRegistry
from analytics_assistant.connectors.base import BaseConnector
from analytics_assistant.connectors.postgres import PostgresConnector
from analytics_assistant.connectors.mysql import MySQLConnector
from analytics_assistant.connectors.sqlite import SQLiteConnector
from analytics_assistant.connectors.sqlserver import SQLServerConnector

class RegistryTests(TestCase):
    def test_registry_registration(self):
        engines = ConnectorRegistry.get_supported_engines()
        self.assertIn("postgres", engines)
        self.assertIn("mysql", engines)
        self.assertIn("sqlite", engines)
        self.assertIn("sqlserver", engines)
        
    def test_get_connector_class(self):
        cls = ConnectorRegistry.get_connector_class("postgres")
        self.assertEqual(cls, PostgresConnector)
        
    def test_get_connector_instance(self):
        inst = ConnectorRegistry.get_connector("mysql")
        self.assertIsInstance(inst, MySQLConnector)

class PostgresConnectorTests(TestCase):
    def setUp(self):
        self.connector = PostgresConnector()
        self.config = {"host": "localhost", "database": "test", "username": "user", "password": ""}
        
    @patch('psycopg.connect')
    def test_test_connection_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        success, msg = self.connector.test_connection(self.config)
        self.assertTrue(success)
        mock_connect.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('psycopg.connect')
    def test_discover_tables(self, mock_connect):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [("users",), ("orders",)]
        mock_cur.__enter__.return_value = mock_cur
        mock_conn.cursor.return_value = mock_cur
        mock_connect.return_value = mock_conn
        
        tables = self.connector.discover_tables(self.config)
        self.assertEqual(tables, ["users", "orders"])


class MySQLConnectorTests(TestCase):
    def setUp(self):
        self.connector = MySQLConnector()
        self.config = {"host": "localhost", "database": "test", "username": "user", "password": ""}
        
    @patch('pymysql.connect')
    def test_test_connection_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        # In case pymysql isn't installed, we might get an ImportError
        from analytics_assistant.connectors.mysql import HAS_PYMYSQL
        if not HAS_PYMYSQL:
            self.skipTest("pymysql not installed")
            
        success, msg = self.connector.test_connection(self.config)
        self.assertTrue(success)


class SQLiteConnectorTests(TestCase):
    def setUp(self):
        self.connector = SQLiteConnector()
        
    @patch('sqlite3.connect')
    @patch('os.path.exists', return_value=True)
    def test_test_connection_success(self, mock_exists, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        config = {"db_path": "/fake/path.db"}
        success, msg = self.connector.test_connection(config)
        self.assertTrue(success)


class SQLServerConnectorTests(TestCase):
    def setUp(self):
        self.connector = SQLServerConnector()
        self.config = {"server": "localhost", "database": "test", "username": "user", "password": ""}
        
    @patch('pyodbc.connect')
    def test_test_connection_success(self, mock_connect):
        mock_conn = MagicMock()
        mock_connect.return_value = mock_conn
        
        from analytics_assistant.connectors.sqlserver import HAS_PYODBC
        if not HAS_PYODBC:
            self.skipTest("pyodbc not installed")
            
        success, msg = self.connector.test_connection(self.config)
        self.assertTrue(success)

from rest_framework.test import APIClient
from django.urls import reverse
import pandas as pd
from analytics_assistant.models import DatasetUpload, DatasetVersion

class SQLServerIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('ingest_connector_table')
        
    @patch('analytics_assistant.connector_pipeline.fetch_table_data')
    def test_sqlserver_ingestion_pipeline(self, mock_fetch):
        # Mock fetch_table_data to return a valid DataFrame
        df = pd.DataFrame({'id': [1, 2], 'name': ['test1', 'test2']})
        mock_fetch.return_value = df
        
        payload = {
            "engine": "sqlserver",
            "server": "localhost",
            "database": "test_db",
            "table": "dbo.test_table",
            "name": "SQL Server Ingest Test"
        }
        
        response = self.client.post(self.url, data=payload, format='json')
        self.assertEqual(response.status_code, 200)
        
        # Verify DatasetUpload was created
        upload_id = response.data.get('upload_id')
        self.assertIsNotNone(upload_id)
        
        upload = DatasetUpload.objects.get(id=upload_id)
        self.assertEqual(upload.name, "SQL Server Ingest Test")
        self.assertEqual(upload.source_type, "sqlserver")
        
        # Verify DatasetVersion was created via persist_dataset_activation
        version = DatasetVersion.objects.filter(dataset=upload).first()
        self.assertIsNotNone(version)
        self.assertEqual(version.row_count, 2)
