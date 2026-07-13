"""Shared dataset profiling helpers used by views and analytics."""

import pandas as pd


def profile_for_blueprint(df: pd.DataFrame) -> dict:
    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    category_columns = [c for c in df.columns if c not in numeric_columns]
    date_column = next(
        (col for col in df.columns if "date" in col.lower() or "time" in col.lower()),
        "",
    )
    return {
        "rows": int(len(df)),
        "columns": df.columns.tolist(),
        "numeric_columns": numeric_columns,
        "category_columns": category_columns,
        "date_column": date_column,
    }
