import re
import pandas as pd

try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False

from .base import BaseConnector
from .registry import ConnectorRegistry
from analytics_assistant.crypto import decrypt_password


@ConnectorRegistry.register("mysql")
class MySQLConnector(BaseConnector):
    """
    MySQL database connector.
    """
    
    @property
    def engine_name(self) -> str:
        return "mysql"
        
    @property
    def display_name(self) -> str:
        return "MySQL"
        
    def _get_connection(self, config: dict):
        if not HAS_PYMYSQL:
            raise ImportError("pymysql is required for MySQLConnector. Install with `pip install pymysql`.")
            
        password = decrypt_password(config.get("password", ""))
        conn = pymysql.connect(
            host=config.get("host"),
            port=int(config.get("port", 3306)),
            database=config.get("database"),
            user=config.get("username"),
            password=password,
            connect_timeout=5,
        )
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
                cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
                tables = [row[0] for row in cur.fetchall()]
                return tables
        finally:
            conn.close()

    def discover_views(self, config: dict) -> list[str]:
        conn = self._get_connection(config)
        try:
            with conn.cursor() as cur:
                cur.execute("SHOW FULL TABLES WHERE Table_type = 'VIEW'")
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
                cur.execute(f"SELECT * FROM `{table_name}`")
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
                df = pd.DataFrame(rows, columns=columns)
                return df
        finally:
            conn.close()
