"""KPI card construction for generic and ads analytics modes."""

import pandas as pd

KPI_MIN = 4
KPI_MAX = 8


def infer_kpi_format(column_name: str, value: float) -> str:
    lowered = column_name.lower()
    if lowered in {"roas", "roi", "margin"}:
        return "decimal"
    if "rate" in lowered or "ratio" in lowered or lowered.endswith("_pct") or "margin" in lowered:
        return "percent"
    if any(token in lowered for token in ("revenue", "sales", "profit", "spend", "cost", "amount")):
        return "currency"
    if isinstance(value, float) and not value.is_integer():
        return "decimal"
    return "number"


def kpi_card(key: str, label: str, value: float | int, column_hint: str = "") -> dict:
    numeric = float(value)
    return {
        "key": key,
        "label": label,
        "value": round(numeric, 4) if abs(numeric) < 1 else round(numeric, 2),
        "format": infer_kpi_format(column_hint or key, numeric),
    }


def clamp_kpi_cards(cards: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen = set()
    for card in cards:
        card_key = card.get("key")
        if card_key in seen:
            continue
        seen.add(card_key)
        deduped.append(card)
    if len(deduped) > KPI_MAX:
        return deduped[:KPI_MAX]
    return deduped


def build_kpi_cards_for_metrics(df, metric_cols: list[str], extras: list[dict] | None = None) -> list[dict]:
    cards: list[dict] = list(extras or [])
    for col in metric_cols:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        cards.append(kpi_card(f"{col}_total", f"Total {col}", float(series.sum()), col))
        if len(cards) >= KPI_MAX:
            break
        cards.append(kpi_card(f"{col}_average", f"Average {col}", float(series.mean()), col))
        if len(cards) >= KPI_MAX:
            break

    if len(cards) < KPI_MIN:
        cards.append(kpi_card("records", "Total Records", int(len(df)), "records"))
    if len(cards) < KPI_MIN and len(df.columns):
        cards.append(kpi_card("columns", "Tracked Fields", int(len(df.columns)), "columns"))

    if len(cards) < KPI_MAX and "Sales" in df.columns and "Profit" in df.columns:
        sales_total = float(pd.to_numeric(df["Sales"], errors="coerce").sum())
        profit_total = float(pd.to_numeric(df["Profit"], errors="coerce").sum())
        if sales_total:
            cards.append(
                kpi_card(
                    "profit_margin",
                    "Profit Margin",
                    (profit_total / sales_total) * 100,
                    "profit_margin",
                )
            )

    return clamp_kpi_cards(cards)


def build_ads_kpi_cards(
    revenue_total: float,
    orders_total: int,
    ad_spend_total: float,
    conversion_avg: float,
    roas: float,
    by_day: pd.DataFrame,
) -> list[dict]:
    days_active = max(int(by_day["date"].nunique()), 1) if not by_day.empty else 1
    avg_order_value = revenue_total / orders_total if orders_total else 0.0
    cost_per_order = ad_spend_total / orders_total if orders_total else 0.0
    avg_daily_revenue = revenue_total / days_active
    avg_daily_orders = orders_total / days_active

    cards = [
        kpi_card("revenue_total", "Total Revenue", revenue_total, "revenue"),
        kpi_card("orders_total", "Total Orders", orders_total, "orders"),
        kpi_card("ad_spend_total", "Total Ad Spend", ad_spend_total, "ad_spend"),
        kpi_card("roas", "Return on Ad Spend", roas, "roas"),
        kpi_card("average_conversion_rate", "Avg Conversion Rate", conversion_avg, "conversion_rate"),
        kpi_card("avg_order_value", "Avg Order Value", avg_order_value, "revenue"),
        kpi_card("cost_per_order", "Cost Per Order", cost_per_order, "ad_spend"),
        kpi_card("avg_daily_revenue", "Avg Daily Revenue", avg_daily_revenue, "revenue"),
        kpi_card("avg_daily_orders", "Avg Daily Orders", avg_daily_orders, "orders"),
    ]
    return clamp_kpi_cards(cards)
