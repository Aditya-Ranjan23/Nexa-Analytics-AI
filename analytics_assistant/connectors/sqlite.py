import re
import os
import sqlite3
import pandas as pd

from .base import BaseConnector
from .registry import ConnectorRegistry

@ConnectorRegistry.register("sqlite")
class SQLiteConnector(BaseConnector):
    """
    SQLite database connector.
    """
    
    @property
    def engine_name(self) -> str:
        return "sqlite"
        
    @property
    def display_name(self) -> str:
        return "SQLite"
        
    def _get_connection(self, config: dict):
        db_path = config.get("db_path")
        if not db_path or not os.path.exists(db_path):
            raise FileNotFoundError(f"SQLite database file not found at {db_path}")
        # uri=True allows read-only mode if needed, but defaults to basic connect
        conn = sqlite3.connect(db_path)
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
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cur.fetchall()]
            return tables
        finally:
            conn.close()

    def discover_views(self, config: dict) -> list[str]:
        conn = self._get_connection(config)
        try:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='view';")
            views = [row[0] for row in cur.fetchall()]
            return views
        finally:
            conn.close()

    def fetch_table(self, config: dict, table_name: str) -> pd.DataFrame:
        conn = self._get_connection(config)
        try:
            if not re.match(r"^[a-zA-Z0-9_]+$", table_name):
                raise ValueError("Invalid table name characters.")
                
            df = pd.read_sql_query(f'SELECT * FROM "{table_name}"', conn)
            return df
        finally:
            conn.close()
