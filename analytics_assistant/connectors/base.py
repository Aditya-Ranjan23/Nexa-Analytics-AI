from abc import ABC, abstractmethod
import pandas as pd


class BaseConnector(ABC):
    """
    Abstract base class for all database connectors.
    Enforces a consistent interface for testing connections, discovering schema,
    and fetching data.
    """
    
    @property
    @abstractmethod
    def engine_name(self) -> str:
        """Return the unique identifier for the engine (e.g., 'postgres', 'mysql')."""
        pass
        
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Return the human-readable name of the engine."""
        pass

    @abstractmethod
    def test_connection(self, config: dict) -> tuple[bool, str]:
        """
        Test the database connection using the provided configuration.
        Returns:
            (success, message)
        """
        pass

    @abstractmethod
    def discover_tables(self, config: dict) -> list[str]:
        """
        Discover user tables in the database.
        """
        pass

    def discover_views(self, config: dict) -> list[str]:
        """
        Discover views in the database (optional). Defaults to returning an empty list.
        """
        return []

    @abstractmethod
    def fetch_table(self, config: dict, table_name: str) -> pd.DataFrame:
        """
        Fetch all rows from the specified table.
        """
        pass

    def connection_metadata(self) -> dict:
        """
        Return metadata about the connector capabilities.
        """
        return {
            "engine": self.engine_name,
            "name": self.display_name,
            "supports_views": type(self).discover_views != BaseConnector.discover_views
        }
