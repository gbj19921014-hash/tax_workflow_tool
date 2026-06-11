from datetime import datetime


MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
MONTH_NUMBER = {month: index for index, month in enumerate(MONTHS, start=1)}


def natural_quarter_periods(period):
    try:
        year_text, quarter_text = period.strip().upper().split("-")
        year = int(year_text)
        quarter = int(quarter_text.removeprefix("Q"))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("自然季度格式应为 YYYY-Q1，例如 2026-Q1。") from error
    if quarter not in (1, 2, 3, 4):
        raise ValueError("自然季度只能是 Q1、Q2、Q3 或 Q4。")
    start = (quarter - 1) * 3
    return [f"{year}-{month}" for month in MONTHS[start : start + 3]]


def detect_natural_quarter(activity_periods):
    normalized = sorted(set(activity_periods), key=_month_sort_key)
    if len(normalized) != 3:
        return None
    first_year, first_month = normalized[0].split("-")
    quarter = (MONTH_NUMBER[first_month] - 1) // 3 + 1
    period = f"{first_year}-Q{quarter}"
    return period if normalized == natural_quarter_periods(period) else None


def period_to_iso_months(period):
    period = period.strip().upper()
    if "-Q" in period:
        activity_periods = natural_quarter_periods(period)
    else:
        activity_periods = [period]
    try:
        return [datetime.strptime(value, "%Y-%b").strftime("%Y-%m") for value in activity_periods]
    except ValueError as error:
        raise ValueError("算税期间格式无效。") from error


def _month_sort_key(value):
    try:
        year_text, month = value.split("-")
        return int(year_text), MONTH_NUMBER[month]
    except (KeyError, ValueError):
        return 9999, 99
