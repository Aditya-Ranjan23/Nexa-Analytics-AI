import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _clean_response(text: str) -> str:
    return _sanitize_model_output(text.strip())


def _sanitize_model_output(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Drop common instruction echo from models that repeat the prompt.
    echo_markers = (
        "you are a senior business analyst",
        "you are an analytics assistant",
        "dataset profile:",
        "formatting rules:",
        "rules:",
    )
    lowered = cleaned.lower()
    if any(marker in lowered for marker in echo_markers):
        parts = cleaned.split("\n\n")
        bullet_parts = [part for part in parts if part.lstrip().startswith(("-", "*", "•"))]
        if bullet_parts:
            cleaned = "\n\n".join(bullet_parts)
        else:
            for idx, line in enumerate(cleaned.splitlines()):
                stripped = line.strip()
                if stripped.startswith(("-", "*", "•")) or (
                    idx > 0 and stripped and not stripped.lower().startswith("you are")
                ):
                    cleaned = "\n".join(cleaned.splitlines()[idx:]).strip()
                    break

    return cleaned.strip()


def _nvidia_chat(messages: list[dict], temperature: float, max_tokens: int) -> str:
    response = requests.post(
        f"{settings.NVIDIA_BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.NVIDIA_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=40,
    )
    response.raise_for_status()
    data = response.json()
    return _clean_response(data["choices"][0]["message"]["content"])


def _local_fallback(user_prompt: str, analytics_snapshot: dict) -> str:
    kpis = analytics_snapshot.get("kpis") or {}
    records = analytics_snapshot.get("records", 0)
    mode = analytics_snapshot.get("dataset_mode", "generic")

    if mode == "ads" and {"revenue_total", "orders_total", "roas"}.issubset(kpis):
        summary = (
            f"Current revenue is {kpis['revenue_total']}, orders are {kpis['orders_total']}, "
            f"and ROAS is {kpis['roas']}."
        )
    elif kpis:
        preview = ", ".join(f"{key}={value}" for key, value in list(kpis.items())[:4])
        summary = f"Dataset has {records} records. Key metrics: {preview}."
    else:
        summary = f"Dataset has {records} records."

    return (
        "NVIDIA API key is not configured yet. "
        f"{summary} You asked: '{user_prompt}'. "
        "Add NVIDIA_API_KEY in .env to enable AI-generated responses."
    )


def ask_nvidia_assistant(
    user_prompt: str, analytics_snapshot: dict, memory_context: str = ""
) -> str:
    if not settings.NVIDIA_API_KEY:
        return _local_fallback(user_prompt, analytics_snapshot)

    prompt = (
        "Be concise, practical, and data-grounded.\n"
        "You may use markdown tables and bullet points.\n"
        "Use numbers from the analytics snapshot.\n\n"
        f"Conversation context:\n{memory_context or 'No previous context.'}\n\n"
        f"Analytics snapshot:\n{json.dumps(analytics_snapshot)}\n\n"
        f"User question: {user_prompt}"
    )

    try:
        return _nvidia_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an analytics assistant for business users. "
                        "Reply with ONLY the answer. Never repeat the question, "
                        "instructions, or raw JSON snapshot."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )
    except requests.RequestException as exc:
        logger.warning("NVIDIA chat request failed: %s", exc)
        return (
            "I could not reach NVIDIA API right now. "
            "Please verify your API key, model, and network, then try again."
        )


def generate_dataset_brief(profile: dict) -> str:
    fallback = (
        "Dataset summary is generated from basic statistics only. "
        "Add NVIDIA_API_KEY to enable deeper business narrative insights."
    )
    if not settings.NVIDIA_API_KEY:
        return fallback

    prompt = (
        "Summarize the dataset profile below for a business dashboard.\n"
        f"Dataset profile:\n{json.dumps(profile)}"
    )
    try:
        return _nvidia_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior business analyst. Output ONLY 3-5 markdown bullet points. "
                        "Mention trend direction, strongest segment, and one risk. "
                        "Use exact numbers from the profile. "
                        "Never repeat instructions, rules, or the raw profile text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.15,
            max_tokens=260,
        )
    except requests.RequestException:
        return fallback


def generate_dashboard_blueprint(profile: dict) -> dict:
    fallback = {
        "kpi_columns": profile.get("numeric_columns", [])[:4],
        "trend": {
            "date_column": profile.get("date_column", ""),
            "metric_column": (profile.get("numeric_columns") or [""])[0],
        },
        "dimension_column": (profile.get("category_columns") or [""])[0],
        "insight_focus": [
            "trend direction",
            "top contributing segments",
            "data quality risks",
        ],
    }
    if not settings.NVIDIA_API_KEY:
        return fallback

    prompt = f"Design a dashboard blueprint from this dataset profile:\n{json.dumps(profile)}"
    try:
        content = _nvidia_chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return ONLY valid JSON with this schema:\n"
                        "{\n"
                        '  "kpi_columns": ["col1","col2"],\n'
                        '  "trend": {"date_column":"...", "metric_column":"..."},\n'
                        '  "dimension_column": "...",\n'
                        '  "insight_focus": ["...", "...", "..."]\n'
                        "}\n"
                        "Use only column names from the profile. No markdown, no explanation."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=350,
        )
        if content.startswith("```"):
            content = content.strip("`")
            content = content.replace("json", "", 1).strip()
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            return fallback
        return parsed
    except (requests.RequestException, json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Dashboard blueprint generation failed, using fallback: %s", exc)
        return fallback
