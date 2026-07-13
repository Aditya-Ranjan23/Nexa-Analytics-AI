import logging
import re

import pandas as pd
from django.db import connection

from django.conf import settings

from .dataset_pipeline import DEFAULT_SEED_PATH  # Single source of truth (TD-017)

logger = logging.getLogger(__name__)

_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class BaseDataSource:
    def load(self) -> pd.DataFrame:
        raise NotImplementedError


class CsvDataSource(BaseDataSource):
    def load(self) -> pd.DataFrame:
        if not DEFAULT_SEED_PATH.exists():
            logger.warning("Default seed dataset missing at %s", DEFAULT_SEED_PATH)
            return pd.DataFrame()
        return pd.read_csv(DEFAULT_SEED_PATH)


class PostgresDataSource(BaseDataSource):
    def load(self) -> pd.DataFrame:
        table_name = getattr(settings, "ANALYTICS_TABLE", "analytics_sales")
        if not _TABLE_NAME_RE.match(table_name):
            logger.error("Invalid ANALYTICS_TABLE name: %s", table_name)
            raise ValueError("ANALYTICS_TABLE must be a valid SQL identifier.")
        query = f'SELECT * FROM "{table_name}"'
        logger.debug("Loading analytics data from PostgreSQL table %s", table_name)
        return pd.read_sql_query(query, connection)


def get_data_source() -> BaseDataSource:
    source = getattr(settings, "ANALYTICS_SOURCE", "csv")
    if source == "csv":
        return CsvDataSource()
    if source == "postgres":
        return PostgresDataSource()
    logger.warning("Unknown ANALYTICS_SOURCE=%s; falling back to CSV", source)
    return CsvDataSource()
