import csv
from datetime import datetime
from io import StringIO
from urllib.request import urlopen


ECB_DAILY_CSV_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.csv"
ECB_HISTORICAL_CSV_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.csv"
ECB_DATA_API_URL = "https://data-api.ecb.europa.eu/service/data/EXR"
SUPPORTED_CURRENCIES = ("PLN", "SEK", "GBP")


def month_to_iso(month):
    try:
        return datetime.strptime(month, "%Y-%b").strftime("%Y-%m")
    except ValueError as error:
        raise ValueError("算税月格式应为 YYYY-MMM，例如 2026-FEB。") from error


def fetch_ecb_rates_to_eur(currencies=SUPPORTED_CURRENCIES, timeout=15):
    with urlopen(ECB_DAILY_CSV_URL, timeout=timeout) as response:
        text = response.read().decode("utf-8-sig")

    rows = list(csv.DictReader(StringIO(text)))
    if not rows:
        raise ValueError("ECB 没有返回汇率数据。")

    row = rows[0]
    rates = {"EUR": 1.0}
    for currency in currencies:
        value = row.get(currency)
        if not value:
            raise ValueError(f"ECB 数据里没有 {currency} 汇率。")
        eur_to_currency = float(value)
        rates[currency] = round(1 / eur_to_currency, 8)

    return {
        "date": row.get("Date", ""),
        "source": "ECB",
        "rates": rates,
    }


def calculate_ecb_monthly_rates_to_eur(text, month, currencies=SUPPORTED_CURRENCIES):
    month_start = month_to_iso(month)

    month_rows = [
        row
        for row in csv.DictReader(StringIO(text))
        if str(row.get("Date", "")).startswith(month_start)
    ]
    if not month_rows:
        raise ValueError(f"ECB 历史数据中没有 {month} 的汇率。")

    rates = {"EUR": 1.0}
    for currency in currencies:
        quotes = []
        for row in month_rows:
            value = row.get(currency)
            if value and str(value).strip():
                quotes.append(float(value))
        if not quotes:
            raise ValueError(f"ECB {month} 数据里没有 {currency} 汇率。")

        average_eur_to_currency = sum(quotes) / len(quotes)
        rates[currency] = round(1 / average_eur_to_currency, 8)

    dates = sorted(row["Date"] for row in month_rows)
    return {
        "month": month,
        "date_range": f"{dates[0]} 至 {dates[-1]}",
        "observation_count": len(month_rows),
        "source": "ECB月平均",
        "rates": rates,
    }


def fetch_ecb_monthly_rates_to_eur(month, currencies=SUPPORTED_CURRENCIES, timeout=30):
    iso_month = month_to_iso(month)
    rates = {"EUR": 1.0}
    observations = {}

    for currency in currencies:
        url = (
            f"{ECB_DATA_API_URL}/M.{currency}.EUR.SP00.A"
            f"?startPeriod={iso_month}&endPeriod={iso_month}&format=csvdata"
        )
        with urlopen(url, timeout=timeout) as response:
            text = response.read().decode("utf-8-sig")

        rows = list(csv.DictReader(StringIO(text)))
        row = next((item for item in rows if item.get("TIME_PERIOD") == iso_month), None)
        if not row or not row.get("OBS_VALUE"):
            raise ValueError(f"ECB Data API 中没有 {month} 的 {currency} 月平均汇率。")

        eur_to_currency = float(row["OBS_VALUE"])
        rates[currency] = round(1 / eur_to_currency, 8)
        observations[currency] = eur_to_currency

    return {
        "month": month,
        "date_range": iso_month,
        "observation_count": len(observations),
        "source": "ECB月平均",
        "ecb_quotes_per_eur": observations,
        "rates": rates,
    }
