import pandas as pd

from run_workflow import EU_COUNTRIES, exchange_to_eur, is_blank
from tax_periods import natural_quarter_periods


ALLOWED_CURRENCIES = ("EUR", "PLN", "SEK", "GBP")
AMOUNT_COLUMN = "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL"
VAT_RATE = 0.22


def summarize_spain(code, name, rule, rows, period, rates):
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


def build_spain_payload(input_file, period, config):
    source = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    expected_months = natural_quarter_periods(period)
    actual_months = sorted(source["ACTIVITY_PERIOD"].dropna().str.strip().str.upper().unique())
    if set(actual_months) != set(expected_months):
        raise ValueError(
            f"CSV 的 B 列月份与 {period} 不一致。应包含：{'、'.join(expected_months)}；"
            f"实际包含：{'、'.join(actual_months) or '无'}。"
        )

    non_commingling = ~source["TRANSACTION_TYPE"].eq("COMMINGLING_BUY")
    seller = source["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
    allowed_currency = source["TRANSACTION_CURRENCY_CODE"].isin(ALLOWED_CURRENCIES)
    buyer_vat_blank = is_blank(source["BUYER_VAT_NUMBER"])
    buyer_vat_has_value = ~buyer_vat_blank
    vat_rate = pd.to_numeric(source["PRICE_OF_ITEMS_VAT_RATE_PERCENT"], errors="coerce")
    vat_not_blank_not_zero = ~is_blank(source["PRICE_OF_ITEMS_VAT_RATE_PERCENT"]) & vat_rate.ne(0)
    vat_blank = is_blank(source["PRICE_OF_ITEMS_VAT_RATE_PERCENT"])
    common = non_commingling & seller & allowed_currency

    part_1 = source[
        common
        & vat_not_blank_not_zero
        & buyer_vat_has_value
        & source["SALE_DEPART_COUNTRY"].eq("ES")
        & source["SALE_ARRIVAL_COUNTRY"].isin(EU_COUNTRIES)
    ]
    part_2 = source[
        common
        & vat_not_blank_not_zero
        & buyer_vat_blank
        & source["SALE_DEPART_COUNTRY"].isin(EU_COUNTRIES)
        & source["SALE_ARRIVAL_COUNTRY"].eq("ES")
    ]
    part_3 = source[
        common
        & vat_blank
        & buyer_vat_blank
        & source["SALE_DEPART_COUNTRY"].isin(EU_COUNTRIES)
        & source["SALE_ARRIVAL_COUNTRY"].eq("ES")
    ]

    rates = config["exchange_rates_to_eur"]
    sections = [
        summarize_spain(
            "1",
            "第一部分",
            "F!=COMMINGLING_BUY；CQ=SELLER；AE!=0且AE!=空白；CA=有数值；BP=ES；BQ=欧盟国家；BB=GBP/EUR/SEK/PLN；B列仅校验季度。",
            part_1,
            period,
            rates,
        ),
        summarize_spain(
            "2",
            "第二部分",
            "F!=COMMINGLING_BUY；CQ=SELLER；AE!=0且AE!=空白；CA=空白；BP=欧盟国家；BQ=ES；BB=GBP/EUR/SEK/PLN；B列仅校验季度。",
            part_2,
            period,
            rates,
        ),
        summarize_spain(
            "3",
            "第三部分",
            "F!=COMMINGLING_BUY；CQ=SELLER；AE=空白；CA=空白；BP=欧盟国家；BQ=ES；BB=GBP/EUR/SEK/PLN；B列仅校验季度。",
            part_3,
            period,
            rates,
        ),
    ]
    summary = [section["summary"] for section in sections]
    currency = [row for section in sections for row in section["currency"]]
    detail = [row for section in sections for row in section["detail"]]
    eur_total = round(sum(row["EUR金额总和"] for row in summary), 2)
    missing_rates = sum(row["缺少汇率行数"] for row in summary)
    tax = round(eur_total / (1 + VAT_RATE) * VAT_RATE, 2)
    return {
        "source_file": str(input_file),
        "activity_period": period,
        "activity_periods": expected_months,
        "tax_country": "ES",
        "country_name": "西班牙",
        "vat_rate": VAT_RATE,
        "registered_vat_countries": sorted(config["registered_vat_countries"]),
        "rates_for_period": rates.get(period, {}),
        "exchange_rate_source": config.get("exchange_rate_source", "config.json"),
        "summary": summary,
        "currency": currency,
        "detail": detail,
        "final": [
            {"项目": "1-3部分命中EUR总和", "金额EUR": eur_total},
            {"项目": "税金", "公式": "1-3部分命中EUR总和/1.22*0.22", "金额EUR": tax, "缺少汇率行数": missing_rates},
        ],
    }
