import re
import psycopg
import pandas as pd

from .base import BaseConnector
from .registry import ConnectorRegistry
from analytics_assistant.crypto import decrypt_password


@ConnectorRegistry.register("postgres")
class PostgresConnector(BaseConnector):
    """
    PostgreSQL database connector.
    """
    
    @property
    def engine_name(self) -> str:
        return "postgres"
        
    @property
    def display_name(self) -> str:
        return "PostgreSQL"
        
    def _get_connection(self, config: dict):
        password = decrypt_password(config.get("password", ""))
        conn = psycopg.connect(
            host=config.get("host"),
            port=int(config.get("port", 5432)),
            dbname=config.get("database"),
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
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]
                return tables
        finally:
            conn.close()

    def discover_views(self, config: dict) -> list[str]:
        conn = self._get_connection(config)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.views 
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
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
                cur.execute(f'SELECT * FROM "{table_name}"')
                rows = cur.fetchall()
                columns = [desc[0] for desc in cur.description] if cur.description else []
                df = pd.DataFrame(rows, columns=columns)
                return df
        finally:
            conn.close()
