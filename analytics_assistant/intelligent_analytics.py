"""Intelligent analytics engine for proactive business anomaly, trend and narrative insights."""

import json
import logging
import numpy as np
import pandas as pd
from django.conf import settings
from .column_utils import business_numeric_cols, pick_primary_metric

logger = logging.getLogger(__name__)


def run_intelligent_analytics(df: pd.DataFrame, dataset_name: str, source_type: str) -> dict:
    """
    Orchestrates proactive anomaly detection, trend intelligence,
    root cause drilldown, narrative writing, and recommended actions.
    Returns a structured dictionary of proactive insights.
    """
    if df.empty:
        return {}

    # 1. Profile data
    numeric_cols = business_numeric_cols(df)
    category_cols = [c for c in df.columns if c not in numeric_cols]
    
    # Resolve date column
    date_col = None
    for col in df.columns:
        if col.lower() in ("date", "timestamp", "created_at", "day"):
            date_col = col
            break
    if not date_col:
        for col in category_cols:
            if "date" in col.lower() or "time" in col.lower():
                date_col = col
                break

    # 2. Anomaly Detection
    anomalies = []
    missing_sum = int(df.isna().sum().sum())
    total_cells = len(df) * len(df.columns)
    missing_ratio = missing_sum / total_cells if total_cells > 0 else 0
    
    if missing_sum > 0:
        anomalies.append({
            "type": "missing_values",
            "metric": "all_cells",
            "message": f"Detected {missing_sum} missing cell values ({round(missing_ratio * 100, 1)}% of dataset).",
            "confidence": round(1.0 - missing_ratio, 2)
        })

    dup_count = int(df.duplicated().sum())
    if dup_count > 0:
        anomalies.append({
            "type": "duplicates",
            "metric": "rows",
            "message": f"Found {dup_count} duplicate records in the dataset. Consider cleaning row duplicates.",
            "confidence": 1.0
        })

    # Outliers, Spikes & Drops
    primary_metric = pick_primary_metric(numeric_cols)
    if primary_metric:
        series = df[primary_metric].dropna()
        if len(series) >= 5:
            mean_val = float(series.mean())
            std_val = float(series.std())
            if std_val > 0:
                # Z-Score Outliers
                outliers = df[np.abs((df[primary_metric] - mean_val) / std_val) > 2.5]
                if not outliers.empty:
                    anomalies.append({
                        "type": "outliers",
                        "metric": primary_metric,
                        "message": f"Found {len(outliers)} statistical outlier records for {primary_metric} exceeding 2.5 standard deviations.",
                        "confidence": 0.85
                    })
                
                # Spikes & Drops (sequential chronological checks if date exists)
                if date_col:
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
                                anomalies.append({
                                    "type": "spike",
                                    "metric": primary_metric,
                                    "message": f"Detected sudden {primary_metric} spike of {round(r['pct_change'] * 100, 1)}% on {str(r[date_col])[:10]}.",
                                    "confidence": 0.90
                                })
                            for _, r in drops.tail(2).iterrows():
                                anomalies.append({
                                    "type": "drop",
                                    "metric": primary_metric,
                                    "message": f"Detected sudden {primary_metric} drop of {round(r['pct_change'] * 100, 1)}% on {str(r[date_col])[:10]}.",
                                    "confidence": 0.90
                                })
                    except Exception as e:
                        logger.warning("Spike/Drop check failed: %s", e)

    # 3. Trend Intelligence
    trends = []
    if primary_metric:
        series = df[primary_metric].dropna()
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

    # 4. Root Cause Analysis
    contributors = []
    dimension_col = None
    for col in category_cols:
        if col.lower() in ("channel", "region", "product", "category", "segment"):
            dimension_col = col
            break
    if not dimension_col and category_cols:
        dimension_col = category_cols[0]

    if dimension_col and primary_metric:
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

    # 5. Top KPIs calculation
    from .column_utils import rank_business_metrics
    ranked_cols = rank_business_metrics(numeric_cols)
    top_kpis = []
    for col in ranked_cols[:3]:
        col_series = pd.to_numeric(df[col], errors="coerce").dropna()
        if not col_series.empty:
            total_val = float(col_series.sum())
            avg_val = float(col_series.mean())
            
            # Infer format
            from .kpi_engine import infer_kpi_format
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
        series = df[primary_metric].dropna()
        if not series.empty:
            max_val = float(series.max())
            from .kpi_engine import infer_kpi_format
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
                        f"Peak Metric: {primary_metric} reached its maximum record of {formatted_max} on {peak_date}."
                    )
                except Exception:
                    business_highlights.append(f"Peak Metric: {primary_metric} reached a peak record of {formatted_max}.")
            else:
                business_highlights.append(f"Peak Metric: {primary_metric} reached a peak record of {formatted_max}.")

    for t in trends:
        if t["type"] == "growth":
            business_highlights.append(f"Growth Indicator: {t['message']}")
            break

    if health_score >= 0.9:
        business_highlights.append(
            f"Clean Ingestion: Strong data profile ({health_grade} - {int(health_score * 100)}% complete) across all rows."
        )
    
    if not business_highlights:
        business_highlights.append(f"Performance Tracking: Active dataset holds {len(df)} records across {len(df.columns)} fields.")

    # 8. Largest Changes
    largest_changes = []
    for a in anomalies:
        if a["type"] in ("spike", "drop"):
            largest_changes.append(a["message"])
        elif a["type"] == "outliers":
            largest_changes.append(f"Outlier Event: {a['message']}")
    for t in trends:
        if t["type"] == "decline":
            largest_changes.append(f"Downward Shift: {t['message']}")
        elif t["type"] == "flat":
            largest_changes.append(f"Stabilization: {t['message']}")
    if not largest_changes:
        largest_changes.append("No sudden spikes, drops, or outlier events detected in this data series.")

    # Suggested questions and recommendations fallback
    heuristics_questions = [
        f"What caused the largest shifts in {primary_metric or 'our core metrics'}?",
        f"Which category under {dimension_col or 'dimensions'} drives the highest volume?",
        "Are there specific data quality gaps we should address?",
    ]
    if primary_metric:
        heuristics_questions.append(f"How can we stabilize the trend in {primary_metric}?")
    if dimension_col:
        heuristics_questions.append(f"What is the forecast contribution of the top {dimension_col}?")

    heuristics_recs = []
    if missing_sum > 0:
        heuristics_recs.append("Data audit: Investigate source tracking systems to fill missing values.")
    if dup_count > 0:
        heuristics_recs.append("Deduplication: Clean duplicate records to prevent dashboard inflation.")
    if contributors:
        heuristics_recs.append(f"Focus target: Reallocate resources or marketing spend to double down on '{contributors[0]['category']}'.")
    if anomalies:
        for a in anomalies:
            if a["type"] == "drop":
                heuristics_recs.append(f"Mitigation plan: Investigate the drop in {a['metric']} immediately.")
                break
    if not heuristics_recs:
        heuristics_recs.append("Monitoring: Maintain active ingestion checks to verify stream stability.")
        heuristics_recs.append("Expansion: Add regional or demographic dimensions to expand audience insights.")

    # Narrative Generation
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
                '  "recommendations": ["Rec 1", "Rec 2", "Rec 3"],\n'
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
        exec_desc = f"Analyzing {len(df)} records for dataset '{dataset_name}' loaded via {source_type}."
        if primary_metric:
            exec_desc += f" Core analysis is centered around metric '{primary_metric}'."
        if trends:
            exec_desc += f" {trends[0]['message']}"
            
        mgt_desc = "Management review indicates data flow remains stable. "
        if contributors:
            mgt_desc += f"Strategic focus is centered on the leading contributor segment '{contributors[0]['category']}' which holds {contributors[0]['share_pct']}% volume share."
        
        ops_desc = "Daily ingestion processes show regular capture frequencies."
        if missing_sum > 0 or dup_count > 0:
            ops_desc += f" Attention is required on data quality: {missing_sum} missing items and {dup_count} duplicate rows found."

        risk_desc = "No critical risk threats detected in this data cycle."
        for a in anomalies:
            if a["type"] in ("drop", "outliers"):
                risk_desc = f"Alert: {a['message']}"
                break

        opp_desc = "Analysis points to growth options. "
        if trends and trends[0]["type"] == "growth":
            opp_desc += f"Positive momentum detected: {trends[0]['message']}"
        elif contributors:
            opp_desc += f"Leverage leading category '{contributors[0]['category']}' to increase market capture."

        narratives = {
            "executive_summary": exec_desc,
            "management_summary": mgt_desc,
            "operational_summary": ops_desc,
            "risk_summary": risk_desc,
            "opportunity_summary": opp_desc,
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
