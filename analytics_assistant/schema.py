ADS_COLUMNS = {"date", "channel", "revenue", "orders", "ad_spend", "conversion_rate"}


def validate_dataset_columns(columns: list[str]) -> tuple[bool, list[str], str]:
    normalized = {col.strip() for col in columns}
    if len(normalized) < 2:
        return False, ["at least 2 columns required"], "invalid"
    missing_ads = sorted(ADS_COLUMNS - normalized)
    mode = "ads" if len(missing_ads) == 0 else "generic"
    return True, [], mode
