from unittest.mock import patch, MagicMock
from django.test import TestCase

from .connectors.registry import ConnectorRegistry
from .connectors.base import BaseConnector
from .connectors.postgres import PostgresConnector
from .connectors.mysql import MySQLConnector
from .connectors.sqlite import SQLiteConnector
from .connectors.sqlserver import SQLServerConnector

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
        from .connectors.mysql import HAS_PYMYSQL
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
        
        from .connectors.sqlserver import HAS_PYODBC
        if not HAS_PYODBC:
            self.skipTest("pyodbc not installed")
            
        success, msg = self.connector.test_connection(self.config)
        self.assertTrue(success)
