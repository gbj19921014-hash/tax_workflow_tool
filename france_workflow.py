import pandas as pd

from run_workflow import EU_COUNTRIES, exchange_to_eur, is_blank
from tax_periods import natural_quarter_periods


ALLOWED_CURRENCIES = ("EUR", "PLN", "SEK", "GBP")
AMOUNT_COLUMN = "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL"
VAT_RATE = 0.20


def summarize_france(code, name, rule, rows, period, rates):
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


def build_france_payload(input_file, period, config):
    source = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    expected_months = natural_quarter_periods(period)
    actual_months = sorted(source["ACTIVITY_PERIOD"].dropna().str.strip().str.upper().unique())
    if set(actual_months) != set(expected_months):
        raise ValueError(
            f"CSV 的 B 列月份与 {period} 不一致。应包含：{'、'.join(expected_months)}；"
            f"实际包含：{'、'.join(actual_months) or '无'}。"
        )

    seller = source["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
    buyer_vat_blank = is_blank(source["BUYER_VAT_NUMBER"])
    buyer_vat_not_blank = ~buyer_vat_blank
    allowed_currency = source["TRANSACTION_CURRENCY_CODE"].isin(ALLOWED_CURRENCIES)
    vat_rate = pd.to_numeric(source["PRICE_OF_ITEMS_VAT_RATE_PERCENT"], errors="coerce")
    vat_rate_not_zero = ~is_blank(source["PRICE_OF_ITEMS_VAT_RATE_PERCENT"]) & vat_rate.ne(0)
    vat_rate_not_equal_zero = vat_rate.ne(0)

    first_rule = (
        vat_rate_not_zero
        & buyer_vat_not_blank
        & source["SALE_DEPART_COUNTRY"].eq("FR")
        & source["SALE_ARRIVAL_COUNTRY"].isin(EU_COUNTRIES)
    )
    second_rule = (
        vat_rate_not_equal_zero
        & buyer_vat_blank
        & source["SALE_DEPART_COUNTRY"].isin(EU_COUNTRIES)
        & source["SALE_ARRIVAL_COUNTRY"].eq("FR")
    )
    part_a = source[seller & allowed_currency & (first_rule | second_rule)]

    rates = config["exchange_rates_to_eur"]
    sections = [
        summarize_france(
            "A",
            "自行缴税订单",
            "CQ=SELLER；BB=GBP/EUR/SEK/PLN；B列仅校验季度；满足以下任一条件："
            "1）AE非空且不等于0，CA非空，BP=FR，BQ=欧盟国家；"
            "2）AE不等于0，CA空白，BP=欧盟国家，BQ=FR。",
            part_a,
            period,
            rates,
        )
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
        "tax_country": "FR",
        "country_name": "法国",
        "vat_rate": VAT_RATE,
        "registered_vat_countries": sorted(config["registered_vat_countries"]),
        "rates_for_period": rates.get(period, {}),
        "exchange_rate_source": config.get("exchange_rate_source", "config.json"),
        "summary": summary,
        "currency": currency,
        "detail": detail,
        "final": [
            {"项目": "自行缴税订单命中EUR总和", "金额EUR": eur_total},
            {"项目": "税金", "公式": "自行缴税订单命中EUR总和/1.2*0.2", "金额EUR": tax, "缺少汇率行数": missing_rates},
        ],
    }
