from typing import Dict, Type
from .base import BaseConnector

class ConnectorRegistry:
    """
    Central registry for database connectors.
    Handles registration, lookup, and instantiation of connector implementations.
    """
    _registry: Dict[str, Type[BaseConnector]] = {}

    @classmethod
    def register(cls, engine: str):
        """Decorator to register a connector class under a specific engine name."""
        def wrapper(connector_cls: Type[BaseConnector]):
            cls._registry[engine] = connector_cls
            return connector_cls
        return wrapper

    @classmethod
    def get_connector_class(cls, engine: str) -> Type[BaseConnector]:
        """Retrieve a connector class by its engine name."""
        if engine not in cls._registry:
            raise ValueError(f"Connector for engine '{engine}' is not registered.")
        return cls._registry[engine]

    @classmethod
    def get_connector(cls, engine: str) -> BaseConnector:
        """Instantiate and return a connector by its engine name."""
        connector_cls = cls.get_connector_class(engine)
        return connector_cls()

    @classmethod
    def get_supported_engines(cls) -> list[str]:
        """Return a list of supported engine names."""
        return list(cls._registry.keys())

    @classmethod
    def get_capabilities(cls) -> dict:
        """Return capabilities of all registered connectors."""
        return {
            engine: cls.get_connector(engine).connection_metadata()
            for engine in cls._registry
        }
