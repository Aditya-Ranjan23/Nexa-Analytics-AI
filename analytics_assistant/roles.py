ROLE_MAP = {
    "ceo": "ceo",
    "marketing_manager": "marketing_manager",
    "marketing": "marketing_manager",
    "team_member": "team_member",
    "team": "team_member",
}


def normalize_role(raw_role: str) -> str:
    if not raw_role:
        return "team_member"
    return ROLE_MAP.get(raw_role.strip().lower(), "team_member")


def widgets_for_role(role: str) -> list[str]:
    if role == "ceo":
        return ["revenue_total", "orders_total", "roas", "trend_summary", "top_channels"]
    if role == "marketing_manager":
        return [
            "ad_spend_total",
            "roas",
            "average_conversion_rate",
            "top_channels",
            "campaign_actions",
        ]
    return ["revenue_total", "orders_total", "top_channels"]


_NON_KPI_WIDGETS = frozenset({"trend_summary", "top_channels", "campaign_actions"})


def filter_kpi_cards_for_role(cards: list[dict], role: str) -> list[dict]:
    """Return KPI cards scoped to role widgets; keep all cards when none match."""
    widget_keys = {key for key in widgets_for_role(role) if key not in _NON_KPI_WIDGETS}
    if not widget_keys:
        return cards
    filtered = [card for card in cards if card.get("key") in widget_keys]
    return filtered if filtered else cards
