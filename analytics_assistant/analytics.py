"""Analytics payload orchestration (facade over engines + dataset pipeline)."""

import pandas as pd

from .chart_engine import build_ads_charts, build_generic_charts, ensure_minimum_charts
from .column_utils import (
    business_numeric_cols,
    find_dimension_column,
    pick_primary_metric,
    rank_business_metrics,
)
from .dataset_pipeline import active_blueprint, load_active_dataframe
from .insights_engine import build_ai_insights, build_generic_insights
from .kpi_engine import build_ads_kpi_cards, build_kpi_cards_for_metrics
from .models import DatasetUpload
from .services import generate_dataset_brief

ADS_COLUMNS = {"date", "channel", "revenue", "orders", "ad_spend", "conversion_rate"}


def _empty_payload() -> dict:
    return {
        "dataset_mode": "generic",
        "kpi_cards": [],
        "kpis": {},
        "charts": [],
        "trends": [],
        "trend_spec": {"x_key": "", "y_key": "", "y_label": ""},
        "top_dimensions": [],
        "ai_insights": [
            {"headline": "Dataset is empty", "detail": "Upload data to begin.", "severity": "warning"}
        ],
        "ai_summary": "Upload a dataset to generate an AI summary.",
        "records": 0,
        "columns": [],
        "widgets": ["revenue_total", "orders_total", "top_channels"],
    }


def build_generic_payload(
    df,
    dataset_upload: DatasetUpload | None = None,
    blueprint_override: dict | None = None,
) -> dict:
    numeric_cols = business_numeric_cols(df)
    category_cols = [c for c in df.columns if c not in numeric_cols]
    blueprint = active_blueprint(dataset_upload, blueprint_override)
    blueprint_kpis = [col for col in blueprint.get("kpi_columns", []) if col in numeric_cols]
    primary_metric = blueprint.get("trend", {}).get("metric_column")
    if primary_metric not in numeric_cols:
        primary_metric = pick_primary_metric(numeric_cols)

    metric_targets = [col for col in blueprint_kpis if col in numeric_cols]
    for col in rank_business_metrics(numeric_cols):
        if len(metric_targets) >= 4:
            break
        if col not in metric_targets:
            metric_targets.append(col)

    kpi_cards = build_kpi_cards_for_metrics(df, metric_targets)
    kpis = {card["key"]: card["value"] for card in kpi_cards}

    top_dimensions = []
    dimension_col = find_dimension_column(df, category_cols, blueprint)
    if dimension_col:
        if primary_metric:
            grouped = (
                df.groupby(dimension_col, as_index=False)[primary_metric]
                .sum()
                .sort_values(primary_metric, ascending=False)
                .head(5)
            )
            top_dimensions = [
                {
                    "label": row[dimension_col],
                    "value": round(float(row[primary_metric]), 2),
                    "dimension": dimension_col,
                }
                for _, row in grouped.iterrows()
            ]
        else:
            counts = (
                df[dimension_col].astype(str).value_counts().head(5).reset_index().values.tolist()
            )
            top_dimensions = [
                {"label": row[0], "value": int(row[1]), "dimension": dimension_col}
                for row in counts
            ]

    charts = build_generic_charts(df, numeric_cols, category_cols, blueprint, primary_metric)
    charts = ensure_minimum_charts(charts, df, primary_metric, dimension_col)
    trend_rows = []
    trend_spec = {"x_key": "", "y_key": "", "y_label": ""}
    if charts:
        primary_chart = charts[0]
        trend_rows = primary_chart.get("data", [])
        trend_spec = primary_chart.get("spec", trend_spec)

    brief_profile = {
        "rows": int(len(df)),
        "columns": df.columns.tolist(),
        "primary_metric": primary_metric or "",
        "kpis": kpis,
        "trend_preview": trend_rows[-5:] if trend_rows else [],
        "top_dimensions": top_dimensions[:5],
    }
    ai_summary = generate_dataset_brief(brief_profile)

    return {
        "dataset_mode": "generic",
        "kpi_cards": kpi_cards,
        "kpis": kpis,
        "charts": charts,
        "trends": trend_rows,
        "trend_spec": trend_spec,
        "top_dimensions": top_dimensions,
        "ai_insights": build_generic_insights(df, numeric_cols, category_cols),
        "ai_summary": ai_summary,
        "import_meta": blueprint.get("import_meta", {}),
        "records": int(len(df)),
        "columns": df.columns.tolist(),
        "widgets": ["revenue_total", "orders_total", "top_channels"],
    }


def build_ads_payload(df) -> dict:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])
    revenue_total = float(df["revenue"].sum())
    orders_total = int(df["orders"].sum())
    ad_spend_total = float(df["ad_spend"].sum())
    conversion_avg = float(df["conversion_rate"].mean())
    roas = revenue_total / ad_spend_total if ad_spend_total else 0.0

    by_day = (
        df.groupby("date", as_index=False)
        .agg({"revenue": "sum", "orders": "sum", "ad_spend": "sum"})
        .sort_values("date")
    )
    by_day["date"] = by_day["date"].dt.strftime("%Y-%m-%d")

    top_channels = (
        df.groupby("channel", as_index=False)["revenue"]
        .sum()
        .sort_values("revenue", ascending=False)
    )

    kpi_cards = build_ads_kpi_cards(
        revenue_total, orders_total, ad_spend_total, conversion_avg, roas, by_day
    )
    charts = build_ads_charts(by_day, top_channels)

    return {
        "dataset_mode": "ads",
        "kpi_cards": kpi_cards,
        "kpis": {card["key"]: card["value"] for card in kpi_cards},
        "charts": charts,
        "trends": by_day.to_dict(orient="records"),
        "trend_spec": {"x_key": "date", "y_key": "revenue", "y_label": "Revenue"},
        "top_dimensions": [
            {"label": row["channel"], "value": row["revenue"], "dimension": "channel"}
            for _, row in top_channels.head(5).iterrows()
        ],
        "ai_insights": build_ai_insights(df, by_day, top_channels),
        "ai_summary": (
            f"Revenue is {round(revenue_total, 2)} with ROAS {round(roas, 2)}. "
            f"Top channel is {top_channels.iloc[0]['channel']}."
            if len(top_channels) > 0
            else "Ad performance summary is available."
        ),
        "records": int(len(df)),
        "columns": df.columns.tolist(),
        "widgets": [
            "revenue_total",
            "orders_total",
            "ad_spend_total",
            "roas",
            "average_conversion_rate",
            "top_channels",
            "campaign_actions",
        ],
    }


def build_analytics_payload(
    dataset_upload: DatasetUpload | None = None,
    blueprint_override: dict | None = None,
) -> dict:
    df = load_active_dataframe(dataset_upload)
    if df.empty:
        return _empty_payload()

    if not ADS_COLUMNS.issubset(set(df.columns)):
        return build_generic_payload(df, dataset_upload, blueprint_override)

    return build_ads_payload(df)
