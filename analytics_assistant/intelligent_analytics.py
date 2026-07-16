"""Intelligent analytics engine for proactive business anomaly, trend and narrative insights."""

import json
import logging
import math
import numpy as np
import pandas as pd
from django.conf import settings
from .column_utils import (
    business_numeric_cols,
    pick_primary_metric,
    find_date_column,
    find_dimension_column,
)
from .kpi_engine import infer_kpi_format

logger = logging.getLogger(__name__)


def run_intelligent_analytics(
    df: pd.DataFrame, dataset_name: str, source_type: str, dataset_upload=None
) -> dict:
    """
    Orchestrates proactive anomaly detection, trend intelligence,
    root cause drilldown, narrative writing, and recommended actions.
    Returns a structured dictionary of proactive insights.
    """
    if df.empty:
        return {}

    # 1. Profile data
    numeric_cols = business_numeric_cols(df)

    # Resolve date column first
    date_col = find_date_column(df, {})
    if not date_col:
        for col in df.columns:
            if col.lower() in ("date", "timestamp", "created_at", "day"):
                date_col = col
                break
        if not date_col:
            for col in [c for c in df.columns if c not in numeric_cols]:
                if "date" in col.lower() or "time" in col.lower():
                    date_col = col
                    break

    category_cols = [c for c in df.columns if c not in numeric_cols and c != date_col]

    # Resolve primary metric
    primary_metric = pick_primary_metric(numeric_cols)

    # Resolve dimension column
    dimension_col = find_dimension_column(df, category_cols, {})
    if not dimension_col:
        for col in category_cols:
            if col.lower() in ("channel", "region", "product", "category", "segment"):
                dimension_col = col
                break
        if not dimension_col and category_cols:
            dimension_col = category_cols[0]

    # 2. Anomaly Detection (M7.2)
    anomalies = []

    # Missing values
    missing_sum = int(df.isna().sum().sum())
    total_cells = len(df) * len(df.columns)
    missing_ratio = missing_sum / total_cells if total_cells > 0 else 0

    if missing_sum > 0:
        missing_pct = round(missing_ratio * 100, 1)
        null_cols = df.columns[df.isna().any()].tolist()
        null_cols_str = ", ".join(null_cols[:3])
        severity = "critical" if missing_ratio > 0.15 else "high" if missing_ratio > 0.05 else "medium" if missing_ratio > 0.01 else "low"
        
        anomalies.append({
            "type": "missing_values",
            "metric": "all_cells",
            "message": f"Detected {missing_sum} missing cell values ({missing_pct}% of dataset).",
            "what_happened": f"Found {missing_sum} missing or null cell values in table columns.",
            "why_happened": f"Data integration gaps resolved in columns: {null_cols_str}.",
            "business_impact": f"Strips reporting coverage from {missing_pct}% of the dataset, potentially biasing averages.",
            "severity": severity,
            "confidence": round(1.0 - missing_ratio, 2)
        })

    # Duplicate records
    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        dup_ratio = dup_count / len(df)
        dup_pct = round(dup_ratio * 100, 1)
        severity = "critical" if dup_ratio > 0.10 else "high" if dup_ratio > 0.02 else "medium"
        
        anomalies.append({
            "type": "duplicates",
            "metric": "rows",
            "message": f"Found {dup_count} duplicate records in the dataset.",
            "what_happened": f"Detected {dup_count} duplicate row entries.",
            "why_happened": "Double-submission action during user session or database synchronization loops.",
            "business_impact": f"Inflates dataset size by {dup_pct}%, leading to skewed metric counts.",
            "severity": severity,
            "confidence": 1.0
        })

    # Outliers (Z-Score > 2.5 on primary metric)
    outliers_idx = []
    if primary_metric:
        series = pd.to_numeric(df[primary_metric], errors="coerce").dropna()
        if len(series) >= 5:
            mean_val = float(series.mean())
            std_val = float(series.std())
            if std_val > 0:
                z_scores = (series - mean_val) / std_val
                outliers_mask = np.abs(z_scores) > 2.5
                outliers_idx = series[outliers_mask].index.tolist()
                
                if len(outliers_idx) > 0:
                    outlier_vals = series[outliers_mask]
                    non_outlier_vals = series[~outliers_mask]
                    avg_shift_pct = 0.0
                    if not non_outlier_vals.empty:
                        new_mean = float(non_outlier_vals.mean())
                        avg_shift_pct = abs(mean_val - new_mean) / new_mean * 100 if new_mean else 0.0
                    
                    dev_sum = float(np.sum(np.abs(outlier_vals - mean_val)))
                    fmt = infer_kpi_format(primary_metric, dev_sum)
                    if fmt == "currency":
                        dev_formatted = f"${dev_sum:,.2f}" if dev_sum < 1000 else f"${dev_sum:,.0f}"
                    else:
                        dev_formatted = f"{dev_sum:,.1f}"
                        
                    severity = "critical" if avg_shift_pct > 15.0 else "high" if len(outliers_idx) > 3 else "medium"
                    why_happened = f"Statistical outliers in '{primary_metric}' that deviate from standard baseline patterns."
                    if dimension_col:
                        outlier_cats = df.loc[outliers_idx, dimension_col].value_counts()
                        if not outlier_cats.empty:
                            top_cat = outlier_cats.index[0]
                            why_happened = f"Driven primarily by performance spike concentrations within '{top_cat}' under '{dimension_col}'."
                    
                    anomalies.append({
                        "type": "outliers",
                        "metric": primary_metric,
                        "message": f"Found {len(outliers_idx)} statistical outlier records for {primary_metric} exceeding 2.5 standard deviations.",
                        "what_happened": f"Extreme outliers detected in '{primary_metric}' across {len(outliers_idx)} rows.",
                        "why_happened": why_happened,
                        "business_impact": f"Introduces a deviation variance of {dev_formatted}, shifting baseline averages by {round(avg_shift_pct, 1)}%.",
                        "severity": severity,
                        "confidence": 0.85
                    })

    # Sequential chronological check (Spikes & Drops)
    if date_col and primary_metric:
        try:
            sorted_df = df.copy()
            sorted_df[date_col] = pd.to_datetime(sorted_df[date_col], errors="coerce")
            sorted_df = sorted_df.dropna(subset=[date_col]).sort_values(date_col)
            if len(sorted_df) >= 3:
                grouped_dates = sorted_df.groupby(date_col)[primary_metric].sum().reset_index()
                grouped_dates["pct_change"] = grouped_dates[primary_metric].pct_change()
                
                spikes = grouped_dates[grouped_dates["pct_change"] > 0.25]
                drops = grouped_dates[grouped_dates["pct_change"] < -0.25]
                
                for _, r in spikes.tail(2).iterrows():
                    val_pct = round(r['pct_change'] * 100, 1)
                    date_str = str(r[date_col])[:10]
                    why_happened = "Sequential chronological performance increase on this specific date."
                    if dimension_col:
                        day_records = df[df[date_col].astype(str).str.startswith(date_str)]
                        if not day_records.empty:
                            cat_totals = day_records.groupby(dimension_col)[primary_metric].sum()
                            if not cat_totals.empty:
                                top_cat = cat_totals.idxmax()
                                share_pct = cat_totals[top_cat] / cat_totals.sum() * 100
                                why_happened = f"Driven primarily by '{top_cat}' sales volume which accounted for {round(share_pct, 1)}% of total daily volume."
                    
                    severity = "critical" if val_pct > 50 else "high"
                    prev_date_row = grouped_dates[grouped_dates[date_col] < r[date_col]].tail(1)
                    volume_diff = float(r[primary_metric] - prev_date_row.iloc[0][primary_metric]) if not prev_date_row.empty else 0.0
                    fmt = infer_kpi_format(primary_metric, volume_diff)
                    if fmt == "currency":
                        diff_formatted = f"${volume_diff:,.2f}" if abs(volume_diff) < 1000 else f"${volume_diff:,.0f}"
                    else:
                        diff_formatted = f"{volume_diff:,.1f}"
                        
                    anomalies.append({
                        "type": "spike",
                        "metric": primary_metric,
                        "message": f"Detected sudden {primary_metric} spike of {val_pct}% on {date_str}.",
                        "what_happened": f"A sequential volume spike of {val_pct}% occurred on {date_str}.",
                        "why_happened": why_happened,
                        "business_impact": f"Drives a single-day volume increase of {diff_formatted} in '{primary_metric}'.",
                        "severity": severity,
                        "confidence": 0.90
                    })
                    
                for _, r in drops.tail(2).iterrows():
                    val_pct = round(r['pct_change'] * 100, 1)
                    date_str = str(r[date_col])[:10]
                    why_happened = "Sequential chronological performance contraction on this specific date."
                    if dimension_col:
                        day_records = df[df[date_col].astype(str).str.startswith(date_str)]
                        if not day_records.empty:
                            cat_totals = day_records.groupby(dimension_col)[primary_metric].sum()
                            if not cat_totals.empty:
                                top_cat = cat_totals.idxmax()
                                share_pct = cat_totals[top_cat] / cat_totals.sum() * 100
                                why_happened = f"Driver: Attributable to '{top_cat}' volume dropping to {round(share_pct, 1)}% of daily totals."
                    
                    severity = "critical" if abs(val_pct) > 40 else "high"
                    prev_date_row = grouped_dates[grouped_dates[date_col] < r[date_col]].tail(1)
                    volume_diff = float(r[primary_metric] - prev_date_row.iloc[0][primary_metric]) if not prev_date_row.empty else 0.0
                    fmt = infer_kpi_format(primary_metric, volume_diff)
                    if fmt == "currency":
                        diff_formatted = f"${abs(volume_diff):,.2f}" if abs(volume_diff) < 1000 else f"${abs(volume_diff):,.0f}"
                    else:
                        diff_formatted = f"{abs(volume_diff):,.1f}"
                        
                    anomalies.append({
                        "type": "drop",
                        "metric": primary_metric,
                        "message": f"Detected sudden {primary_metric} drop of {abs(val_pct)}% on {date_str}.",
                        "what_happened": f"A sequential volume contraction of {abs(val_pct)}% occurred on {date_str}.",
                        "why_happened": why_happened,
                        "business_impact": f"Reduces single-day metric value by {diff_formatted} in '{primary_metric}'.",
                        "severity": severity,
                        "confidence": 0.90
                    })
        except Exception as e:
            logger.warning("Spike/Drop check failed: %s", e)

    # Flat trends
    if primary_metric:
        series = pd.to_numeric(df[primary_metric], errors="coerce").dropna()
        if len(series) >= 2:
            first_val = float(series.iloc[0])
            last_val = float(series.iloc[-1])
            diff = last_val - first_val
            pct = (diff / first_val * 100) if first_val else 0
            if abs(pct) <= 2:
                severity = "high" if primary_metric.lower() in ("sales", "revenue", "profit") else "medium"
                anomalies.append({
                    "type": "flat",
                    "metric": primary_metric,
                    "message": f"Primary metric {primary_metric} remained flat (change of {round(pct, 1)}%) over the active period.",
                    "what_happened": f"Stagnation in '{primary_metric}' performance trend.",
                    "why_happened": "Absence of growth catalysts or promotional spikes during this active scope.",
                    "business_impact": f"Indicates growth stagnation with a flat net change of {round(pct, 1)}% across records.",
                    "severity": severity,
                    "confidence": 0.70
                })

    # Schema changes compared to previous version
    if dataset_upload:
        try:
            from .models import DatasetVersion
            current_v = getattr(dataset_upload, "active_version_number", 1)
            if current_v > 1:
                prev_v = dataset_upload.versions.filter(version_number=current_v - 1).first()
                if prev_v and prev_v.ai_blueprint:
                    old_cols = [c["name"] for c in prev_v.ai_blueprint.get("columns", [])]
                    new_cols = df.columns.tolist()
                    added = list(set(new_cols) - set(old_cols))
                    removed = list(set(old_cols) - set(new_cols))
                    if added or removed:
                        added_str = f"added: {', '.join(added)}" if added else ""
                        removed_str = f"removed: {', '.join(removed)}" if removed else ""
                        comb = " and ".join(filter(None, [added_str, removed_str]))
                        anomalies.append({
                            "type": "schema_change",
                            "metric": "schema",
                            "message": f"Schema modified since version {prev_v.version_number}. {comb.capitalize()}.",
                            "what_happened": f"Changes in table fields detected. {comb.capitalize()}.",
                            "why_happened": "Database restructuring, external schema migration, or CSV layout adjustments.",
                            "business_impact": f"Alters column structure, potentially breaking dashboard charts or data filters.",
                            "severity": "critical",
                            "confidence": 1.0
                        })
        except Exception as e:
            logger.warning("Schema anomaly check failed: %s", e)

    # Unexpected Category Changes
    for col in category_cols:
        from .column_utils import is_id_like_column
        if is_id_like_column(col, df[col].astype(str)):
            continue
        n = len(df)
        if n >= 20:
            if date_col:
                try:
                    sorted_df = df.copy()
                    sorted_df[date_col] = pd.to_datetime(sorted_df[date_col], errors="coerce")
                    sorted_df = sorted_df.dropna(subset=[date_col]).sort_values(date_col)
                    n_sorted = len(sorted_df)
                    half1 = sorted_df.iloc[:n_sorted // 2]
                    half2 = sorted_df.iloc[n_sorted // 2:]
                except Exception:
                    half1 = df.iloc[:n // 2]
                    half2 = df.iloc[n // 2:]
            else:
                half1 = df.iloc[:n // 2]
                half2 = df.iloc[n // 2:]
            
            p1 = half1[col].value_counts(normalize=True).to_dict()
            p2 = half2[col].value_counts(normalize=True).to_dict()
            all_keys = set(p1.keys()) | set(p2.keys())
            for key in all_keys:
                share1 = p1.get(key, 0.0)
                share2 = p2.get(key, 0.0)
                diff = share2 - share1
                if share1 > 0.10 and share2 == 0.0:
                    anomalies.append({
                        "type": "category_shift",
                        "metric": col,
                        "message": f"Category '{key}' in '{col}' has completely disappeared (distribution shifted from {round(share1*100, 1)}% to 0.0%) in the latter half.",
                        "what_happened": f"Category '{key}' disappeared from distribution.",
                        "why_happened": f"Redirection of marketing efforts or tracking integration failures for '{key}' segment.",
                        "business_impact": f"Losing '{key}' completely strips away its historical {round(share1*100, 1)}% volume share.",
                        "severity": "high",
                        "confidence": 0.80
                    })
                elif abs(diff) > 0.15:
                    direction = "increased" if diff > 0 else "decreased"
                    severity = "high" if abs(diff) > 0.25 else "medium"
                    anomalies.append({
                        "type": "category_shift",
                        "metric": col,
                        "message": f"'{key}' share in '{col}' shifted: {direction} from {round(share1*100, 1)}% to {round(share2*100, 1)}%.",
                        "what_happened": f"Category '{key}' distribution shifted.",
                        "why_happened": "Shifts in organic product demand or customer acquisition channel allocation.",
                        "business_impact": f"Displaces {round(abs(diff)*100, 1)}% of total distribution volume for '{key}' in dimension '{col}'.",
                        "severity": severity,
                        "confidence": 0.80
                    })

    # 3. Trend Intelligence (M7.3)
    trends = []
    if primary_metric:
        series = pd.to_numeric(df[primary_metric], errors="coerce").dropna()
        if len(series) >= 2:
            first_val = float(series.iloc[0])
            last_val = float(series.iloc[-1])
            diff = last_val - first_val
            pct = (diff / first_val * 100) if first_val else 0
            if pct > 5:
                trends.append({
                    "type": "growth",
                    "metric": primary_metric,
                    "message": f"{primary_metric} increased by {round(pct, 1)}% from start to end of records.",
                    "confidence": 0.8
                })
            elif pct < -5:
                trends.append({
                    "type": "decline",
                    "metric": primary_metric,
                    "message": f"{primary_metric} decreased by {round(abs(pct), 1)}% from start to end of records.",
                    "confidence": 0.8
                })
            else:
                trends.append({
                    "type": "flat",
                    "metric": primary_metric,
                    "message": f"{primary_metric} remained flat (change of {round(pct, 1)}%) over the active period.",
                    "confidence": 0.7
                })

    # Increase/Decrease tracking on other numeric columns
    numeric_increases = []
    numeric_declines = []
    for col in numeric_cols:
        col_series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(col_series) >= 2:
            first_val = float(col_series.iloc[0])
            last_val = float(col_series.iloc[-1])
            diff = last_val - first_val
            pct = (diff / first_val * 100) if first_val else 0
            if pct > 5:
                numeric_increases.append(f"{col} grew by {round(pct, 1)}%")
            elif pct < -5:
                numeric_declines.append(f"{col} declined by {round(abs(pct), 1)}%")

    # Fastest growing & declining categories
    fastest_grow_cat = None
    largest_dec_cat = None
    if primary_metric and dimension_col:
        try:
            n = len(df)
            if n >= 6:
                if date_col:
                    sorted_df = df.copy()
                    sorted_df[date_col] = pd.to_datetime(sorted_df[date_col], errors="coerce")
                    sorted_df = sorted_df.dropna(subset=[date_col]).sort_values(date_col)
                    n_sorted = len(sorted_df)
                    half1 = sorted_df.iloc[:n_sorted // 2]
                    half2 = sorted_df.iloc[n_sorted // 2:]
                else:
                    half1 = df.iloc[:n // 2]
                    half2 = df.iloc[n // 2:]
                
                sum1 = half1.groupby(dimension_col)[primary_metric].sum()
                sum2 = half2.groupby(dimension_col)[primary_metric].sum()
                
                cat_growths = {}
                for cat in sum1.index:
                    if cat in sum2.index:
                        v1 = sum1[cat]
                        v2 = sum2[cat]
                        if v1 > 0:
                            cat_growths[cat] = ((v2 - v1) / v1) * 100
                
                if cat_growths:
                    sorted_growths = sorted(cat_growths.items(), key=lambda item: item[1])
                    if sorted_growths[-1][1] > 0:
                        fastest_grow_cat = {
                            "category": str(sorted_growths[-1][0]),
                            "growth_pct": round(sorted_growths[-1][1], 1)
                        }
                    if sorted_growths[0][1] < 0:
                        largest_dec_cat = {
                            "category": str(sorted_growths[0][0]),
                            "decline_pct": round(abs(sorted_growths[0][1]), 1)
                        }
        except Exception as e:
            logger.warning("Fastest/decline category checks failed: %s", e)

    # Seasonality indicators
    seasonality_desc = []
    if date_col and primary_metric:
        try:
            temp_df = df.copy()
            temp_df[date_col] = pd.to_datetime(temp_df[date_col], errors="coerce")
            temp_df = temp_df.dropna(subset=[date_col])
            if len(temp_df) >= 14:
                temp_df["day_of_week"] = temp_df[date_col].dt.day_name()
                grouped_dow = temp_df.groupby("day_of_week")[primary_metric].mean()
                dow_mean = grouped_dow.mean()
                dow_std = grouped_dow.std()
                if dow_mean > 0 and (dow_std / dow_mean) > 0.15:
                    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                    weekends = ["Saturday", "Sunday"]
                    weekday_avg = grouped_dow.reindex(weekdays).mean()
                    weekend_avg = grouped_dow.reindex(weekends).mean()
                    if weekday_avg and weekend_avg:
                        diff_pct = ((weekend_avg - weekday_avg) / weekday_avg) * 100
                        if abs(diff_pct) > 20:
                            direction = "higher" if diff_pct > 0 else "lower"
                            seasonality_desc.append(
                                f"Strong day-of-week seasonality: Weekend {primary_metric} averages {round(abs(diff_pct), 1)}% {direction} than weekdays."
                            )
            if len(temp_df) >= 60:
                temp_df["month"] = temp_df[date_col].dt.month_name()
                grouped_month = temp_df.groupby("month")[primary_metric].mean()
                month_mean = grouped_month.mean()
                month_std = grouped_month.std()
                if month_mean > 0 and (month_std / month_mean) > 0.20:
                    peak_month = grouped_month.idxmax()
                    low_month = grouped_month.idxmin()
                    seasonality_desc.append(
                        f"Monthly seasonality: '{peak_month}' exhibits peak average volume, while '{low_month}' is lowest."
                    )
        except Exception as e:
            logger.warning("Seasonality extraction failed: %s", e)

    # Trend Reversals
    reversal_desc = []
    if primary_metric:
        try:
            n = len(df)
            if n >= 15:
                p1 = df.iloc[:n//3][primary_metric].mean()
                p2 = df.iloc[n//3:2*n//3][primary_metric].mean()
                p3 = df.iloc[2*n//3:][primary_metric].mean()
                if p1 is not None and p2 is not None and p3 is not None:
                    if p1 < p2 and p2 > p3:
                        reversal_desc.append(
                            f"Trend Reversal: '{primary_metric}' accelerated in mid-period but declined in the final portion."
                        )
                    elif p1 > p2 and p2 < p3:
                        reversal_desc.append(
                            f"Trend Reversal: '{primary_metric}' contracted mid-period followed by recovery in the final third."
                        )
        except Exception as e:
            logger.warning("Trend reversal checks failed: %s", e)

    # Trend Acceleration & Deceleration
    acceleration_desc = []
    if primary_metric:
        try:
            n = len(df)
            if n >= 20:
                q1 = df.iloc[:n//4][primary_metric].mean()
                q2 = df.iloc[n//4:n//2][primary_metric].mean()
                q3 = df.iloc[n//2:3*n//4][primary_metric].mean()
                q4 = df.iloc[3*n//4:][primary_metric].mean()
                if all(v is not None for v in [q1, q2, q3, q4]):
                    g1 = (q2 - q1) / q1 if q1 else 0
                    g2 = (q4 - q3) / q3 if q3 else 0
                    if g1 > 0 and g2 > g1 + 0.05:
                        acceleration_desc.append(
                            f"Trend Acceleration: Growth rate for '{primary_metric}' accelerated from {round(g1*100, 1)}% in the first half to {round(g2*100, 1)}% in the second half."
                        )
                    elif g1 > 0 and g2 < g1 - 0.05:
                        acceleration_desc.append(
                            f"Trend Deceleration: Growth rate for '{primary_metric}' slowed down from {round(g1*100, 1)}% to {round(g2*100, 1)}% in the latter portion."
                        )
        except Exception as e:
            logger.warning("Acceleration check failed: %s", e)

    # 4. Root Cause Analysis (M7.4)
    contributors = []
    if dimension_col and primary_metric:
        try:
            n = len(df)
            if n >= 6:
                half1 = df.iloc[:n//2]
                half2 = df.iloc[n//2:]
                
                sum1 = half1.groupby(dimension_col)[primary_metric].sum()
                sum2 = half2.groupby(dimension_col)[primary_metric].sum()
                
                total_h1 = sum1.sum()
                total_h2 = sum2.sum()
                net_change = total_h2 - total_h1
                
                if abs(net_change) > 0.01:
                    cat_contribs = []
                    for cat in set(sum1.index) | set(sum2.index):
                        v1 = sum1.get(cat, 0.0)
                        v2 = sum2.get(cat, 0.0)
                        diff = v2 - v1
                        pct_contrib = (diff / net_change) * 100
                        cat_contribs.append({
                            "category": str(cat),
                            "diff": diff,
                            "pct_contrib": round(pct_contrib, 1)
                        })
                    
                    cat_contribs = sorted(cat_contribs, key=lambda item: abs(item["pct_contrib"]), reverse=True)
                    for item in cat_contribs[:3]:
                        contributors.append({
                            "dimension": dimension_col,
                            "category": item["category"],
                            "metric": primary_metric,
                            "share_pct": item["pct_contrib"],
                            "message": f"'{item['category']}' drives the change: contributed {item['pct_contrib']}% of total net {primary_metric} shift.",
                            "confidence": 0.90
                        })
        except Exception as e:
            logger.warning("Root cause breakdown failed: %s", e)

    # If contributors is empty (or no trend change), calculate standard volume shares
    if not contributors and dimension_col and primary_metric:
        try:
            grouped = df.groupby(dimension_col)[primary_metric].sum().reset_index()
            grouped = grouped.sort_values(primary_metric, ascending=False)
            total_val = grouped[primary_metric].sum()
            if total_val > 0:
                top_ctr = grouped.iloc[0]
                pct = (top_ctr[primary_metric] / total_val) * 100
                contributors.append({
                    "dimension": dimension_col,
                    "category": str(top_ctr[dimension_col]),
                    "metric": primary_metric,
                    "share_pct": round(pct, 1),
                    "message": f"'{top_ctr[dimension_col]}' is the largest contributor to {primary_metric}, driving {round(pct, 1)}% of total volume.",
                    "confidence": 0.95
                })
        except Exception as e:
            logger.warning("Contribution volume calculations failed: %s", e)

    # Contradiction Resolution & Cleanup (Objective 7)
    trend_types = [t["type"] for t in trends]
    anomaly_types = [a["type"] for a in anomalies]
    
    if "flat" in trend_types and ("spike" in anomaly_types or "drop" in anomaly_types):
        for a in anomalies:
            if a["type"] == "flat":
                a["message"] = f"Stagnant overall trend for '{primary_metric}' coupled with sequential daily volatility."
                a["why_happened"] = "Daily sequential spike and drop events cancelled each other out, leaving net period performance flat."
                a["severity"] = "medium"

    # De-duplicate sequential events on the exact same date
    seen_dates = set()
    cleaned_anoms = []
    for a in anomalies:
        if a["type"] in ("spike", "drop"):
            try:
                date_part = a["message"].split(" on ")[1].rstrip(".")
                if date_part in seen_dates:
                    continue
                seen_dates.add(date_part)
            except Exception:
                pass
        cleaned_anoms.append(a)
    anomalies = cleaned_anoms

    # Rank anomalies by severity (Objective 3)
    severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    anomalies = sorted(anomalies, key=lambda x: severity_weights.get(x.get("severity", "low"), 1), reverse=True)

    # 5. Top KPIs calculation
    ranked_cols = []
    if numeric_cols:
        from .column_utils import rank_business_metrics
        ranked_cols = rank_business_metrics(numeric_cols)
    
    top_kpis = []
    for col in ranked_cols[:3]:
        col_series = pd.to_numeric(df[col], errors="coerce").dropna()
        if not col_series.empty:
            total_val = float(col_series.sum())
            avg_val = float(col_series.mean())
            fmt = infer_kpi_format(col, total_val)
            top_kpis.append({
                "metric": col,
                "total": total_val,
                "average": avg_val,
                "format": fmt
            })

    # 6. Data Quality Summary
    health_score = round(1.0 - missing_ratio, 2)
    if len(df) > 0 and dup_count > 0:
        dup_ratio = dup_count / len(df)
        health_score = max(0.0, round(health_score - 0.1 * min(dup_ratio, 1.0), 2))
        
    if health_score >= 0.95:
        health_grade = "Excellent"
    elif health_score >= 0.85:
        health_grade = "Good"
    elif health_score >= 0.70:
        health_grade = "Fair"
    else:
        health_grade = "Warning"
        
    data_quality = {
        "missing_cells": missing_sum,
        "missing_pct": round(missing_ratio * 100, 1),
        "duplicate_rows": dup_count,
        "duplicate_pct": round(dup_count / len(df) * 100, 1) if len(df) > 0 else 0,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "health_score": health_score,
        "health_grade": health_grade
    }

    # 7. Business Highlights
    business_highlights = []
    if contributors:
        c = contributors[0]
        business_highlights.append(
            f"Segment Lead: '{c['category']}' dominates '{c['dimension']}', driving {c['share_pct']}% of total {c['metric']} volume."
        )
    if primary_metric:
        series = pd.to_numeric(df[primary_metric], errors="coerce").dropna()
        if not series.empty:
            max_val = float(series.max())
            fmt = infer_kpi_format(primary_metric, max_val)
            if fmt == "currency":
                formatted_max = f"${max_val:,.2f}" if max_val < 1000 else f"${max_val:,.0f}"
            elif fmt == "percent":
                formatted_max = f"{max_val:.1f}%"
            else:
                formatted_max = f"{max_val:,.2f}" if not max_val.is_integer() else f"{int(max_val):,}"
            
            if date_col:
                try:
                    peak_row = df.loc[series.idxmax()]
                    peak_date = str(peak_row[date_col])[:10]
                    business_highlights.append(
                        f"Peak Performance: {primary_metric} reached its maximum record of {formatted_max} on {peak_date}."
                    )
                except Exception:
                    business_highlights.append(f"Peak Performance: {primary_metric} reached a peak record of {formatted_max}.")
            else:
                business_highlights.append(f"Peak Performance: {primary_metric} reached a peak record of {formatted_max}.")

    if trends:
        if trends[0]["type"] == "growth":
            business_highlights.append(f"Growth Indicator: {trends[0]['message']}")
    if seasonality_desc:
        business_highlights.append(seasonality_desc[0])
    if reversal_desc:
        business_highlights.append(reversal_desc[0])
    
    if not business_highlights:
        business_highlights.append(f"Performance Tracking: Active dataset holds {len(df)} records across {len(df.columns)} fields.")

    # 8. Largest Changes (Objective 2: De-duplicate)
    largest_changes = []
    if acceleration_desc:
        largest_changes.append(acceleration_desc[0])
    if reversal_desc:
        largest_changes.append(reversal_desc[0])
        
    for a in anomalies:
        if a["type"] in ("spike", "drop", "category_shift", "schema_change"):
            largest_changes.append(f"Shift Alert: {a['message']}")
            
    # Filter out duplicate summaries
    unique_changes = []
    for c in largest_changes:
        if c not in unique_changes:
            unique_changes.append(c)
    largest_changes = unique_changes[:5]
    
    if not largest_changes:
        largest_changes.append("No sudden structural shifts, drops, or outlier events detected in this data series.")

    # Heuristics Questions (M7.5)
    heuristics_questions = []
    if primary_metric:
        heuristics_questions.append(f"What is driving the overall trend in {primary_metric}?")
    if dimension_col and primary_metric:
        heuristics_questions.append(f"Which {dimension_col} category contributed most to {primary_metric} shifts?")
    if missing_sum > 0:
        heuristics_questions.append(f"How can we isolate rows containing missing fields?")
    
    for a in anomalies:
        if a["type"] == "drop" and " on " in a["message"]:
            try:
                dt_str = a["message"].split(" on ")[1].rstrip(".")
                heuristics_questions.append(f"What caused the sudden drop in {primary_metric} on {dt_str}?")
                break
            except Exception:
                pass
        elif a["type"] == "spike" and " on " in a["message"]:
            try:
                dt_str = a["message"].split(" on ")[1].rstrip(".")
                heuristics_questions.append(f"What caused the sudden spike in {primary_metric} on {dt_str}?")
                break
            except Exception:
                pass
                
    if fastest_grow_cat:
        heuristics_questions.append(f"Why is '{fastest_grow_cat['category']}' growing faster than other {dimension_col} options?")
    if largest_dec_cat:
        heuristics_questions.append(f"What caused the decline in '{largest_dec_cat['category']}'?")
        
    while len(heuristics_questions) < 5:
        heuristics_questions.append("What details can we extract from the data quality health grade?")

    # Heuristics Recommendations (M7.7)
    heuristics_recs = []
    if missing_sum > 0:
        heuristics_recs.append(
            f"Fact: Identified {missing_sum} missing values in the dataset. "
            f"Recommendation: Audit source data collection pipelines to identify the cause of null records. "
            f"Speculation: This is likely due to ingestion API drops or database column default omissions."
        )
    if dup_count > 0:
        heuristics_recs.append(
            f"Fact: Found {dup_count} duplicate rows in the active tables. "
            f"Recommendation: Implement deduplication filters in the connector script or clean source tables. "
            f"Speculation: Duplicate entries often arise from double-submission events or data stream sync overlaps."
        )
    if contributors:
        lead_cat = contributors[0]["category"]
        lead_dim = contributors[0]["dimension"]
        lead_share = contributors[0]["share_pct"]
        heuristics_recs.append(
            f"Fact: Category '{lead_cat}' dominates the '{lead_dim}' dimension with {lead_share}% of total volume. "
            f"Recommendation: Allocate additional inventory, support, and marketing budget to '{lead_cat}'. "
            f"Speculation: This segment may have higher market penetration or seasonal product demand."
        )
    
    drop_anom = next((a for a in anomalies if a["type"] == "drop"), None)
    if drop_anom and " on " in drop_anom["message"]:
        try:
            dt_str = drop_anom["message"].split(" on ")[1].rstrip(".")
            pct_val = drop_anom["message"].split(" drop of ")[1].split("%")[0]
            heuristics_recs.append(
                f"Fact: A sudden drop of {pct_val}% was detected on {dt_str}. "
                f"Recommendation: Run a system service status audit and verify campaign tracking integrity on that date. "
                f"Speculation: Server outages, database locks, or localized payment gateway failures might have occurred."
            )
        except Exception:
            pass

    growth_trend = next((t for t in trends if t["type"] == "growth"), None)
    decline_trend = next((t for t in trends if t["type"] == "decline"), None)
    if growth_trend:
        try:
            pct_val = growth_trend["message"].split(" increased by ")[1].split("%")[0]
            heuristics_recs.append(
                f"Fact: Overall positive growth trend of {pct_val}% detected. "
                f"Recommendation: Capitalize on positive momentum by running user expansion campaigns. "
                f"Speculation: Growth may be propelled by recent organic search improvements or competitive exits."
            )
        except Exception:
            pass
    elif decline_trend:
        try:
            pct_val = decline_trend["message"].split(" decreased by ")[1].split("%")[0]
            heuristics_recs.append(
                f"Fact: Overall negative trend of {pct_val}% detected. "
                f"Recommendation: Conduct customer exit interviews and review pricing/discount incentives. "
                f"Speculation: Competitor promotions or market saturation might be causing the volume contraction."
            )
        except Exception:
            pass

    default_recs = [
        f"Fact: Outlier values detected in '{primary_metric or 'the dataset'}'. Recommendation: Standardize and normalize data validation rules for automated alerts. Speculation: System data logging could be experiencing latency spikes.",
        f"Fact: Dataset has {len(df)} records across {len(df.columns)} columns. Recommendation: Integrate additional demographic or region metadata to broaden analysis depth. Speculation: Deeper segmentation would help isolate local anomalies.",
        f"Fact: Standard tracking systems are active. Recommendation: Establish automated weekly syncs to prevent manual data latency issues. Speculation: Scheduled ingestion prevents dashboard synchronization lag.",
        f"Fact: Column schema contains {len(df.columns)} attributes. Recommendation: Prune unused columns to optimize database storage and query speeds. Speculation: Removing redundant columns reduces page load time.",
        f"Fact: Categorical distribution is concentrated. Recommendation: Expand outreach to secondary markets to diversify customer acquisition sources. Speculation: Relying on a single dominant channel increases channel concentration risk."
    ]
    for r in default_recs:
        if len(heuristics_recs) < 5:
            heuristics_recs.append(r)

    # Narrative Generation Fallback (M7.6 / Objective 8 & 9)
    exec_summary = (
        f"This executive briefing evaluates the performance of '{dataset_name}' loaded via {source_type}. "
        f"Comprising {len(df)} records across {len(df.columns)} attributes, our analysis profiles "
        f"'{primary_metric}' as the primary performance indicator."
    )
    if trends:
        exec_summary += f" Over the active period, we observed that {trends[0]['message'].lower()}"
    else:
        exec_summary += " Over the active period, core indicators remained stable."
        
    if seasonality_desc:
        exec_summary += f" Furthermore, we identified {seasonality_desc[0].lower()}"
        
    if reversal_desc:
        exec_summary += f" Notably, our analysis flags a {reversal_desc[0].lower()}"

    mgt_summary = (
        f"Strategic management review shows performance is heavily driven by category distributions under '{dimension_col}'. "
    )
    if contributors:
        mgt_summary += f"The leading segment '{contributors[0]['category']}' represents a {contributors[0]['share_pct']}% volume share. "
    if fastest_grow_cat:
        mgt_summary += f"Additionally, the fastest-growing category is '{fastest_grow_cat['category']}' expanding by {fastest_grow_cat['growth_pct']}%. "
    if largest_dec_cat:
        mgt_summary += f"Conversely, watch for contraction in '{largest_dec_cat['category']}' which fell by {largest_dec_cat['decline_pct']}%."

    ops_summary = (
        f"Operational data integration completed with a completeness score of {int(data_quality['health_score']*100)}% "
        f"({data_quality['health_grade']}). "
    )
    if data_quality["health_score"] >= 0.90:
        ops_summary += "The database stream is currently healthy with clean record ingestion."
    else:
        ops_summary += (
            f"Hygiene optimization is required due to the presence of {missing_sum} null cells "
            f"and {dup_count} duplicate rows, which may skew reporting accuracy."
        )

    risk_summary = "Risk screening identified no major systemic threats. baseline integrity is intact."
    risk_points = []
    if missing_sum > 0:
        risk_points.append(f"{missing_sum} missing cells")
    if dup_count > 0:
        risk_points.append(f"{dup_count} duplicate records")
    if len(outliers_idx) > 0:
        risk_points.append(f"{len(outliers_idx)} outliers")
    for a in anomalies:
        if a["type"] == "drop" and " on " in a["message"]:
            try:
                dt_str = a["message"].split(" on ")[1].rstrip(".")
                risk_points.append(f"a sudden drop on {dt_str}")
            except Exception:
                pass
    if risk_points:
        risk_summary = f"Alert: High-priority risk vectors identified: {', '.join(risk_points)}. These anomalies skew core reports and warrant direct operational review."

    opp_summary = "Growth opportunity profiling indicates channels for volume expansion."
    if trends and trends[0]["type"] == "growth":
        opp_summary += f" Leverage the positive growth momentum ({trends[0]['message'].split(' increased by ')[1]}) to launch target campaigns."
    if fastest_grow_cat:
        opp_summary += f" Specifically, double-down on the high-momentum '{fastest_grow_cat['category']}' channel which is expanding at {fastest_grow_cat['growth_pct']}%."
    elif contributors:
        opp_summary += f" Focus on customer retention in the dominant segment '{contributors[0]['category']}' to secure market share."

    # Stats profile context
    stats_summary = {
        "dataset_name": dataset_name,
        "source_type": source_type,
        "primary_metric": primary_metric,
        "dimension": dimension_col,
        "anomalies": anomalies,
        "trends": trends,
        "contributors": contributors,
        "rows": len(df),
        "columns": df.columns.tolist(),
        "data_quality": data_quality
    }

    narratives = {}
    if settings.NVIDIA_API_KEY:
        from .services import _nvidia_chat
        try:
            prompt = (
                "You are a junior business analyst writing a concise executive briefing.\n"
                "Ground everything strictly in the facts provided. Never invent or speculate without stating it clearly.\n"
                f"Statistical Profile:\n{json.dumps(stats_summary)}\n\n"
                "Return ONLY valid JSON containing these exact string keys:\n"
                '{\n'
                '  "executive_summary": "Paragraph summarizing performance and dataset context.",\n'
                '  "management_summary": "Paragraph focused on general management overview.",\n'
                '  "operational_summary": "Paragraph focused on daily operations and data quality.",\n'
                '  "risk_summary": "Paragraph detailing threats or drops found.",\n'
                '  "opportunity_summary": "Paragraph highlighting positive trends or segments.",\n'
                '  "recommendations": ["Fact: [Observed Fact] Recommendation: [Action] Speculation: [Speculation]", ...],\n'
                '  "suggested_questions": ["Question 1", "Question 2", "Question 3"]\n'
                '}\n'
                "Output ONLY JSON. Do not include markdown wraps."
            )
            content = _nvidia_chat(
                messages=[
                    {"role": "system", "content": "You are a professional business intelligence narrative generator. Output valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.15,
                max_tokens=650
            )
            if content.startswith("```"):
                content = content.strip("`")
                content = content.replace("json", "", 1).strip()
            parsed = json.loads(content)
            narratives = parsed
        except Exception as e:
            logger.warning("NVIDIA Proactive Insights generation failed: %s", e)

    if not narratives:
        narratives = {
            "executive_summary": exec_summary,
            "management_summary": mgt_summary,
            "operational_summary": ops_summary,
            "risk_summary": risk_summary,
            "opportunity_summary": opp_summary,
            "recommendations": heuristics_recs[:5],
            "suggested_questions": heuristics_questions[:5]
        }

    return {
        "anomalies": anomalies[:5],
        "trends": trends[:5],
        "contributors": contributors[:5],
        "narratives": narratives,
        "top_kpis": top_kpis,
        "data_quality": data_quality,
        "business_highlights": business_highlights[:5],
        "largest_changes": largest_changes[:5],
        "confidence_score": health_score
    }
