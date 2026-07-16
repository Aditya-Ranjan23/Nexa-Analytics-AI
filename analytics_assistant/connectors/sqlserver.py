import re
import pandas as pd

try:
    import pyodbc
    HAS_PYODBC = True
except ImportError:
    HAS_PYODBC = False

from .base import BaseConnector
from .registry import ConnectorRegistry
from analytics_assistant.crypto import decrypt_password


@ConnectorRegistry.register("sqlserver")
class SQLServerConnector(BaseConnector):
    """
    SQL Server database connector.
    """
    
    @property
    def engine_name(self) -> str:
        return "sqlserver"
        
    @property
    def display_name(self) -> str:
        return "SQL Server"
        
    def _get_connection(self, config: dict):
        if not HAS_PYODBC:
            raise ImportError("pyodbc is required for SQLServerConnector. Install with `pip install pyodbc`.")
            
        password = decrypt_password(config.get("password", ""))
        server = config.get("server")
        database = config.get("database")
        username = config.get("username")
        
        # Build connection string
        driver = config.get("driver", "{ODBC Driver 17 for SQL Server}")
        
        # If integrated security / windows auth is selected
        if config.get("windows_auth", False):
            conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
        else:
            conn_str = f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};"
            
        conn = pyodbc.connect(conn_str, timeout=5)
        return conn

    def test_connection(self, config: dict) -> tuple[bool, str]:
        try:
            conn = self._get_connection(config)
            conn.close()
            return True, "Connection successful."
        except Exception as e:
            return False, str(e)

    def discover_tables(self, config: dict) -> list[str]:
        conn = self._get_connection(config)
        try:
            with conn.cursor() as cur:
                # Exclude system tables
                cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_NAME != 'sysdiagrams'")
                tables = [row[0] for row in cur.fetchall()]
                return tables
        finally:
            conn.close()

    def discover_views(self, config: dict) -> list[str]:
        conn = self._get_connection(config)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_NAME != 'sysdiagrams'")
                views = [row[0] for row in cur.fetchall()]
                return views
        finally:
            conn.close()

    def fetch_table(self, config: dict, table_name: str) -> pd.DataFrame:
        conn = self._get_connection(config)
        try:
            if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                raise ValueError("Invalid table name characters.")
                
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM [{table_name}]")
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
                # Ensure pyodbc row objects are converted to list/tuple for DataFrame
                df = pd.DataFrame([tuple(r) for r in rows], columns=columns)
                return df
        finally:
            conn.close()
