"""Auto-detected insight cards for ads and generic analytics modes."""


def build_ai_insights(df, by_day, top_channels) -> list[dict]:
    insights = []

    if len(top_channels) >= 2:
        leader = top_channels.iloc[0]
        runner_up = top_channels.iloc[1]
        gap_pct = (
            ((leader["revenue"] - runner_up["revenue"]) / runner_up["revenue"]) * 100
            if runner_up["revenue"]
            else 0
        )
        insights.append(
            {
                "headline": f"{leader['channel']} outperforming {runner_up['channel']}",
                "detail": (
                    f"{leader['channel']} revenue is {round(gap_pct, 1)}% higher "
                    f"({round(leader['revenue'], 0)} vs {round(runner_up['revenue'], 0)})."
                ),
                "severity": "info",
            }
        )

    meta_df = df[df["channel"] == "Meta Ads"].sort_values("date")
    if len(meta_df) >= 2:
        first_rate = float(meta_df.iloc[0]["conversion_rate"])
        last_rate = float(meta_df.iloc[-1]["conversion_rate"])
        if first_rate > 0:
            drop_pct = ((first_rate - last_rate) / first_rate) * 100
            if drop_pct >= 8:
                insights.append(
                    {
                        "headline": f"Meta Ads CTR dropped {round(drop_pct, 0)}% (proxy signal)",
                        "detail": (
                            "Conversion efficiency declined from the first to latest window. "
                            "Review creatives, audience overlap, and landing-page intent match."
                        ),
                        "severity": "warning",
                    }
                )

    recent = by_day.tail(3)
    if len(recent) == 3:
        growth_1 = recent.iloc[1]["revenue"] - recent.iloc[0]["revenue"]
        growth_2 = recent.iloc[2]["revenue"] - recent.iloc[1]["revenue"]
        if growth_2 <= growth_1 * 0.75:
            insights.append(
                {
                    "headline": "Revenue trend likely to plateau",
                    "detail": (
                        "Recent daily growth is slowing versus the previous interval. "
                        "Add new campaign experiments and optimize high-intent segments."
                    ),
                    "severity": "warning",
                }
            )

    if not insights:
        insights.append(
            {
                "headline": "Performance remains stable",
                "detail": "No major warning signals detected in the latest period.",
                "severity": "info",
            }
        )

    return insights[:3]


def build_generic_insights(df, numeric_cols, category_cols) -> list[dict]:
    insights = []
    if numeric_cols:
        top_numeric = numeric_cols[0]
        mean_val = float(df[top_numeric].mean())
        insights.append(
            {
                "headline": f"{top_numeric} is the strongest tracked metric",
                "detail": f"Average {top_numeric} is {round(mean_val, 2)} across {len(df)} rows.",
                "severity": "info",
            }
        )
    if category_cols:
        col = category_cols[0]
        counts = df[col].astype(str).value_counts().head(1)
        if not counts.empty:
            insights.append(
                {
                    "headline": f"{counts.index[0]} dominates {col}",
                    "detail": f"Top category appears {int(counts.iloc[0])} times.",
                    "severity": "info",
                }
            )
    missing_ratio = df.isna().sum().sum() / (len(df) * max(len(df.columns), 1))
    if missing_ratio > 0.05:
        insights.append(
            {
                "headline": "Data quality warning",
                "detail": f"Missing values are {round(missing_ratio * 100, 1)}% of dataset cells.",
                "severity": "warning",
            }
        )
    if not insights:
        insights.append(
            {
                "headline": "Dataset loaded successfully",
                "detail": "No major warning signals detected.",
                "severity": "info",
            }
        )
    return insights[:3]
