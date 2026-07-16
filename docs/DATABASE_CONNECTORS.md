# Database Connectors Guide

Nexa Analytics AI provides a flexible Database Connector Framework allowing you to ingest datasets directly from relational and non-relational database systems. 

## Supported Connectors

Nexa currently supports the following database connectors out-of-the-box:

- **PostgreSQL**: Connect to any standard PostgreSQL database.
- **MySQL**: Connect to MySQL databases.
- **SQL Server**: Connect to Microsoft SQL Server and SQL Server Express instances (with support for Windows Authentication).
- **SQLite**: Ingest data directly from local SQLite database files.

*Note: Snowflake, BigQuery, Redshift, Oracle, and MongoDB support is planned for future releases.*

## Connector Architecture

The connector framework is built on a registry pattern. All database connectors inherit from `BaseConnector` in `analytics_assistant/connectors/base.py`. This interface enforces four methods that every connector must implement:

1. `test_connection(config: dict) -> Tuple[bool, str]`
2. `discover_tables(config: dict) -> List[str]`
3. `discover_views(config: dict) -> List[str]`
4. `fetch_table(config: dict, table: str) -> pd.DataFrame`

Connectors are registered into the system using the `@ConnectorRegistry.register("engine_name")` decorator.

## Adding a New Connector

To add a new database connector, follow these steps:

1. Create a new file in `analytics_assistant/connectors/` (e.g., `oracle.py`).
2. Implement a subclass of `BaseConnector`.
3. Decorate it with `@ConnectorRegistry.register('oracle')`.
4. Import your new module in `analytics_assistant/connectors/__init__.py`.
5. Update `models.py` to include your new engine in `DatasetUpload.SOURCE_CHOICES`.
6. Add the relevant UI form to `templates/analytics_assistant/dashboard.html` and register it in `dashboard.js` via `bindDatabaseConnector('oraclePrefix', 'oracle')`.
