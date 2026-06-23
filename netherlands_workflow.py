import pandas as pd

from run_workflow import EU_COUNTRIES, exchange_to_eur
from tax_periods import natural_quarter_periods


ALLOWED_CURRENCIES = ("EUR", "PLN", "SEK", "GBP")
AMOUNT_COLUMN = "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL"
VAT_RATE = 0.21


def _vat_rate_is_21_percent(values):
    rates = pd.to_numeric(values, errors="coerce")
    return rates.sub(VAT_RATE).abs().lt(0.000001)


def summarize_netherlands(code, name, rule, rows, period, rates):
    rows = rows.copy()
    rows["_original_amount"] = pd.to_numeric(rows[AMOUNT_COLUMN], errors="coerce").fillna(0.0)
    rows["_eur_amount"] = [
        exchange_to_eur(amount, currency, period, rates)
        for amount, currency in zip(rows["_original_amount"], rows["TRANSACTION_CURRENCY_CODE"])
    ]
    currency_rows = []
    for currency in ALLOWED_CURRENCIES:
        part = rows[rows["TRANSACTION_CURRENCY_CODE"].fillna("").eq(currency)]
        currency_rows.append(
            {
                "项目": code,
                "币种": currency,
                "行数": int(len(part)),
                "原币合计": round(float(part["_original_amount"].sum()), 2),
                "折EUR金额": round(float(part["_eur_amount"].dropna().sum()), 2),
                "缺少汇率行数": int(part["_eur_amount"].isna().sum()),
            }
        )
    eur_total = round(float(rows["_eur_amount"].dropna().sum()), 2)
    return {
        "summary": {
            "项目": code,
            "名称": name,
            "筛选口径": rule,
            "命中行数": int(len(rows)),
            "金额列": AMOUNT_COLUMN,
            "EUR金额总和": eur_total,
            "缺少汇率行数": int(rows["_eur_amount"].isna().sum()),
            "税率": VAT_RATE,
            "税金EUR": round(eur_total / (1 + VAT_RATE) * VAT_RATE, 2),
        },
        "currency": currency_rows,
        "detail": rows.assign(项目=code, 项目名称=name).to_dict("records"),
    }


def build_netherlands_payload(input_file, period, config):
    source = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    expected_months = natural_quarter_periods(period)
    actual_months = sorted(source["ACTIVITY_PERIOD"].dropna().str.strip().str.upper().unique())
    if set(actual_months) != set(expected_months):
        raise ValueError(
            f"CSV 的 B 列月份与 {period} 不一致。应包含：{'、'.join(expected_months)}；"
            f"实际包含：{'、'.join(actual_months) or '无'}。"
        )

    registered_eu = set(config["registered_vat_countries"]) & EU_COUNTRIES
    unregistered_eu = EU_COUNTRIES - registered_eu
    allowed_currency = source["TRANSACTION_CURRENCY_CODE"].isin(ALLOWED_CURRENCIES)
    vat_21 = _vat_rate_is_21_percent(source["PRICE_OF_ITEMS_VAT_RATE_PERCENT"])

    seller_a = source[
        source["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
        & source["SALE_ARRIVAL_COUNTRY"].eq("NL")
        & vat_21
        & allowed_currency
    ]
    seller_b = source[
        source["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
        & source["SALE_DEPART_COUNTRY"].eq("NL")
        & source["SALE_ARRIVAL_COUNTRY"].isin(unregistered_eu)
        & vat_21
        & allowed_currency
    ]

    rates = config["exchange_rates_to_eur"]
    sections = [
        summarize_netherlands(
            "A",
            "Seller A：目的国NL",
            "CQ=SELLER；BQ=NL；AE=0.21；BP不限制；BB=GBP/EUR/SEK/PLN；B列仅校验季度。",
            seller_a,
            period,
            rates,
        ),
        summarize_netherlands(
            "B",
            "Seller B：NL发往未注册税号欧盟国家",
            "CQ=SELLER；BP=NL；BQ=欧盟国家且排除已注册税号国家；AE=0.21；BB=GBP/EUR/SEK/PLN；B列仅校验季度。",
            seller_b,
            period,
            rates,
        ),
    ]
    summary = [section["summary"] for section in sections]
    currency = [row for section in sections for row in section["currency"]]
    detail = [row for section in sections for row in section["detail"]]
    seller_total = round(sum(row["EUR金额总和"] for row in summary), 2)
    missing_rates = sum(row["缺少汇率行数"] for row in summary)
    tax = round(seller_total / (1 + VAT_RATE) * VAT_RATE, 2)
    return {
        "source_file": str(input_file),
        "activity_period": period,
        "activity_periods": expected_months,
        "tax_country": "NL",
        "country_name": "荷兰",
        "vat_rate": VAT_RATE,
        "registered_vat_countries": sorted(config["registered_vat_countries"]),
        "unregistered_eu_countries": sorted(unregistered_eu),
        "rates_for_period": rates.get(period, {}),
        "exchange_rate_source": config.get("exchange_rate_source", "config.json"),
        "summary": summary,
        "currency": currency,
        "detail": detail,
        "final": [
            {"项目": "Seller部分总销售额", "金额EUR": seller_total},
            {"项目": "税金", "公式": "Seller部分总销售额/1.21*0.21", "金额EUR": tax, "缺少汇率行数": missing_rates},
        ],
    }
