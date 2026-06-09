import csv
from io import StringIO
from urllib.request import urlopen


ECB_DAILY_CSV_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.csv"
SUPPORTED_CURRENCIES = ("PLN", "SEK", "GBP")


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
