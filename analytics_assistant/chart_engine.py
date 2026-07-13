"""Chart construction for generic and ads analytics modes."""

import pandas as pd

from .column_utils import find_date_column, find_dimension_column, rank_business_metrics

CHART_MIN = 2
CHART_MAX = 4


def clamp_charts(charts: list[dict]) -> list[dict]:
    valid = [chart for chart in charts if chart.get("data")]
    if len(valid) > CHART_MAX:
        return valid[:CHART_MAX]
    return valid


def build_chart(
    chart_id: str,
    title: str,
    subtitle: str,
    chart_type: str,
    data: list[dict],
    x_key: str,
    y_key: str,
    y_label: str = "",
) -> dict:
    return {
        "id": chart_id,
        "title": title,
        "subtitle": subtitle,
        "type": chart_type,
        "data": data,
        "spec": {
            "x_key": x_key,
            "y_key": y_key,
            "y_label": y_label or y_key,
        },
    }


def time_series_rows(
    df, date_col: str, metric_col: str, max_points: int = 24
) -> tuple[list[dict], str]:
    temp = df[[date_col, metric_col]].copy()
    temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
    temp = temp.dropna(subset=[date_col, metric_col])
    if temp.empty:
        return [], ""

    unique_dates = temp[date_col].nunique()
    if unique_dates > max_points:
        temp["period"] = temp[date_col].dt.to_period("M").astype(str)
        grouped = (
            temp.groupby("period", as_index=False)[metric_col]
            .sum()
            .sort_values("period")
            .tail(max_points)
        )
        x_key = "period"
    else:
        grouped = (
            temp.groupby(date_col, as_index=False)[metric_col]
            .sum()
            .sort_values(date_col)
            .tail(max_points)
        )
        grouped[date_col] = grouped[date_col].dt.strftime("%Y-%m-%d")
        x_key = date_col

    return grouped.rename(columns={x_key: x_key}).to_dict(orient="records"), x_key


def dimension_bar_rows(df, dimension_col: str, metric_col: str, limit: int = 8) -> list[dict]:
    grouped = (
        df.groupby(dimension_col, as_index=False)[metric_col]
        .sum()
        .sort_values(metric_col, ascending=False)
        .head(limit)
    )
    return grouped.to_dict(orient="records")


def ensure_minimum_charts(
    charts: list[dict],
    df,
    primary_metric: str | None,
    dimension_col: str | None,
) -> list[dict]:
    charts = clamp_charts(charts)
    if len(charts) >= CHART_MIN or not primary_metric or primary_metric not in df.columns:
        return charts

    if dimension_col and dimension_col in df.columns:
        fallback_rows = dimension_bar_rows(df, dimension_col, primary_metric, limit=6)
        if fallback_rows and not any(chart.get("id") == "chart-fallback-share" for chart in charts):
            charts.append(
                build_chart(
                    "chart-fallback-share",
                    f"{primary_metric} Breakdown",
                    f"Grouped by {dimension_col}",
                    "doughnut",
                    fallback_rows,
                    dimension_col,
                    primary_metric,
                    primary_metric,
                )
            )

    if len(charts) < CHART_MIN:
        ranked = (
            pd.to_numeric(df[primary_metric], errors="coerce")
            .dropna()
            .sort_values(ascending=False)
            .head(10)
            .reset_index(drop=True)
        )
        if not ranked.empty:
            bucket_rows = [
                {"bucket": f"Rank {idx + 1}", primary_metric: float(value)}
                for idx, value in enumerate(ranked)
            ]
            charts.append(
                build_chart(
                    "chart-fallback-ranked",
                    f"Top {primary_metric} Values",
                    "Highest values in dataset",
                    "bar",
                    bucket_rows,
                    "bucket",
                    primary_metric,
                    primary_metric,
                )
            )

    return clamp_charts(charts)


def build_generic_charts(
    df,
    numeric_cols: list[str],
    category_cols: list[str],
    blueprint: dict,
    primary_metric: str | None,
) -> list[dict]:
    charts: list[dict] = []
    if not numeric_cols:
        return charts

    primary = primary_metric if primary_metric in numeric_cols else numeric_cols[0]
    ranked_metrics = rank_business_metrics(numeric_cols)
    secondary = next((col for col in ranked_metrics if col != primary), primary)
    dimension_col = find_dimension_column(df, category_cols, blueprint)
    date_col = find_date_column(df, blueprint)

    primary_trend = None
    secondary_trend = None
    primary_bar = None
    secondary_bar = None
    share_chart = None

    if date_col:
        trend_rows, x_key = time_series_rows(df, date_col, primary)
        if trend_rows:
            primary_trend = build_chart(
                "chart-trend-primary",
                f"{primary} Trend",
                f"Over time by {x_key}",
                "line",
                trend_rows,
                x_key,
                primary,
                primary,
            )
        if secondary != primary:
            secondary_rows, secondary_x = time_series_rows(df, date_col, secondary)
            if secondary_rows:
                secondary_trend = build_chart(
                    "chart-trend-secondary",
                    f"{secondary} Trend",
                    f"Over time by {secondary_x}",
                    "line",
                    secondary_rows,
                    secondary_x,
                    secondary,
                    secondary,
                )

    if dimension_col:
        bar_rows = dimension_bar_rows(df, dimension_col, primary)
        if bar_rows:
            primary_bar = build_chart(
                "chart-dimension-primary",
                f"{primary} by {dimension_col}",
                "Top performing groups",
                "bar",
                bar_rows,
                dimension_col,
                primary,
                primary,
            )
            share_chart = build_chart(
                "chart-dimension-share",
                f"{primary} Share",
                f"Distribution across {dimension_col}",
                "doughnut",
                bar_rows[:6],
                dimension_col,
                primary,
                primary,
            )
        if secondary != primary:
            secondary_bar_rows = dimension_bar_rows(df, dimension_col, secondary)
            if secondary_bar_rows:
                secondary_bar = build_chart(
                    "chart-dimension-secondary",
                    f"{secondary} by {dimension_col}",
                    "Comparison across groups",
                    "bar",
                    secondary_bar_rows,
                    dimension_col,
                    secondary,
                    secondary,
                )

    for candidate in (primary_trend, primary_bar, share_chart, secondary_trend, secondary_bar):
        if candidate and len(charts) < CHART_MAX:
            charts.append(candidate)

    if not charts and primary:
        ranked = (
            pd.to_numeric(df[primary], errors="coerce")
            .dropna()
            .sort_values(ascending=False)
            .head(12)
            .reset_index(drop=True)
        )
        if not ranked.empty:
            bucket_rows = [
                {"bucket": f"Row {idx + 1}", primary: float(value)}
                for idx, value in enumerate(ranked)
            ]
            charts.append(
                build_chart(
                    "chart-ranked-primary",
                    f"Top {primary} Values",
                    "Highest individual records",
                    "bar",
                    bucket_rows,
                    "bucket",
                    primary,
                    primary,
                )
            )

    return clamp_charts(charts)


def build_ads_charts(by_day: pd.DataFrame, top_channels: pd.DataFrame) -> list[dict]:
    charts: list[dict] = []

    if not by_day.empty:
        revenue_rows = by_day[["date", "revenue"]].to_dict(orient="records")
        charts.append(
            build_chart(
                "chart-revenue-trend",
                "Revenue Trend",
                "Daily revenue performance",
                "line",
                revenue_rows,
                "date",
                "revenue",
                "Revenue",
            )
        )
        spend_rows = by_day[["date", "ad_spend"]].to_dict(orient="records")
        charts.append(
            build_chart(
                "chart-spend-trend",
                "Ad Spend Trend",
                "Daily advertising spend",
                "line",
                spend_rows,
                "date",
                "ad_spend",
                "Ad Spend",
            )
        )

    if not top_channels.empty:
        channel_rows = top_channels.head(8).to_dict(orient="records")
        charts.append(
            build_chart(
                "chart-channel-revenue",
                "Revenue by Channel",
                "Top channels ranked by revenue",
                "bar",
                channel_rows,
                "channel",
                "revenue",
                "Revenue",
            )
        )
        charts.append(
            build_chart(
                "chart-channel-share",
                "Revenue Share by Channel",
                "Contribution mix across channels",
                "doughnut",
                top_channels.head(6).to_dict(orient="records"),
                "channel",
                "revenue",
                "Revenue",
            )
        )

    return clamp_charts(charts)
