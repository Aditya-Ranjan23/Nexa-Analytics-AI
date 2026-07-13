"""Column detection and metric ranking helpers for analytics engines."""

import pandas as pd


def is_id_like_column(col: str, series: pd.Series) -> bool:
    lowered = col.lower().replace(" ", "_")
    if lowered in {"id", "row_id", "index"} or lowered.endswith("_id"):
        return True
    if " id" in col.lower() or col.lower().startswith("id "):
        return True
    if len(series) > 10:
        uniqueness = series.nunique(dropna=True) / len(series)
        if uniqueness > 0.9 and any(token in lowered for token in ("id", "code", "key", "number")):
            return True
    return False


def business_numeric_cols(df) -> list[str]:
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    filtered = []
    for col in numeric_cols:
        series = pd.to_numeric(df[col], errors="coerce")
        if is_id_like_column(col, series):
            continue
        filtered.append(col)
    return filtered or numeric_cols


def rank_business_metrics(numeric_cols: list[str]) -> list[str]:
    priority = ["sales", "revenue", "profit", "quantity", "discount", "cost", "amount", "spend"]
    return sorted(
        numeric_cols,
        key=lambda col: next(
            (idx for idx, token in enumerate(priority) if token in col.lower()),
            len(priority),
        ),
    )


def pick_primary_metric(numeric_cols: list[str]) -> str | None:
    if not numeric_cols:
        return None
    preferred = ["sales", "revenue", "profit", "amount", "value", "cost"]
    lowered = {col.lower(): col for col in numeric_cols}
    for key in preferred:
        for col_lower, original in lowered.items():
            if key in col_lower:
                return original
    return numeric_cols[0]


def find_date_column(df, blueprint: dict) -> str | None:
    candidate = blueprint.get("trend", {}).get("date_column")
    if candidate in df.columns:
        return candidate
    return next(
        (col for col in df.columns if "date" in col.lower() or "time" in col.lower()),
        None,
    )


def find_dimension_column(df, category_cols: list[str], blueprint: dict) -> str | None:
    candidate = blueprint.get("dimension_column", "")
    if candidate in df.columns and not is_id_like_column(candidate, df[candidate].astype(str)):
        return candidate
    ranked = []
    for col in category_cols:
        if is_id_like_column(col, df[col].astype(str)):
            continue
        cardinality = df[col].nunique(dropna=True)
        if 2 <= cardinality <= 25:
            ranked.append((cardinality, col))
    if ranked:
        ranked.sort(key=lambda item: abs(item[0] - 8))
        return ranked[0][1]
    for col in category_cols:
        if not is_id_like_column(col, df[col].astype(str)):
            return col
    return category_cols[0] if category_cols else None
