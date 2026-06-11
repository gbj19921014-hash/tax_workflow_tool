import pandas as pd

from run_workflow import EU_COUNTRIES, basic_tax_number_format_ok, clean_tax_number, exchange_to_eur, is_blank
from tax_periods import natural_quarter_periods


ALLOWED_CURRENCIES = ("EUR", "PLN", "SEK", "GBP")
AMOUNT_COLUMN = "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL"
VAT_RATE = 0.19
REGISTERED_EU_COUNTRIES = {"DE", "ES", "FR", "IT", "NL", "PL"}


def cross_border_vat_format_ok(arrival_country, value):
    cleaned = clean_tax_number(value)
    prefix = "EL" if arrival_country == "GR" else str(arrival_country).upper()
    return bool(cleaned) and cleaned.startswith(prefix)


def summarize_germany(code, name, rule, rows, period, rates):
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


def build_germany_payload(input_file, period, config):
    source = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    expected_months = natural_quarter_periods(period)
    actual_months = sorted(source["ACTIVITY_PERIOD"].dropna().str.strip().str.upper().unique())
    if set(actual_months) != set(expected_months):
        raise ValueError(
            f"CSV 的 B 列月份与 {period} 不一致。应包含：{'、'.join(expected_months)}；"
            f"实际包含：{'、'.join(actual_months) or '无'}。"
        )

    seller = source["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
    non_commingling = ~source["TRANSACTION_TYPE"].eq("COMMINGLING_BUY")
    export_no_blank = source["EXPORT_OUTSIDE_EU"].fillna("").str.strip().str.upper().isin(["", "NO"])
    buyer_vat_blank = is_blank(source["BUYER_VAT_NUMBER"])
    buyer_vat_not_blank = ~buyer_vat_blank
    allowed_currency = source["TRANSACTION_CURRENCY_CODE"].isin(ALLOWED_CURRENCIES)
    vat_rate = pd.to_numeric(source["PRICE_OF_ITEMS_VAT_RATE_PERCENT"], errors="coerce")
    unregistered_eu = EU_COUNTRIES - REGISTERED_EU_COUNTRIES

    common = seller & non_commingling & export_no_blank & allowed_currency
    part_a = source[
        common
        & source["SALE_DEPART_COUNTRY"].isin(EU_COUNTRIES)
        & source["SALE_ARRIVAL_COUNTRY"].eq("DE")
        & buyer_vat_blank
    ]
    part_b = source[
        common
        & source["SALE_DEPART_COUNTRY"].eq("DE")
        & source["SALE_ARRIVAL_COUNTRY"].isin(unregistered_eu)
        & buyer_vat_blank
    ]
    cross_border_valid = pd.Series(
        [
            cross_border_vat_format_ok(country, vat)
            for country, vat in zip(source["SALE_ARRIVAL_COUNTRY"], source["BUYER_VAT_NUMBER"])
        ],
        index=source.index,
    )
    part_c = source[
        common
        & source["SALE_DEPART_COUNTRY"].eq("DE")
        & source["SALE_ARRIVAL_COUNTRY"].isin(EU_COUNTRIES - {"DE"})
        & vat_rate.gt(0)
        & buyer_vat_not_blank
        & ~cross_border_valid
    ]
    self_format_valid = source["BUYER_VAT_NUMBER"].map(basic_tax_number_format_ok)
    part_d = source[
        common
        & source["SALE_DEPART_COUNTRY"].eq("DE")
        & source["SALE_ARRIVAL_COUNTRY"].eq("DE")
        & buyer_vat_not_blank
        & self_format_valid
    ]

    rates = config["exchange_rates_to_eur"]
    sections = [
        summarize_germany("A", "B2C EU→DE", "CQ=SELLER；F非COMMINGLING_BUY；CJ仅NO和空白；BP=欧盟27国；BQ=DE；CA空白；BB=GBP/EUR/SEK/PLN；B列仅校验季度。", part_a, period, rates),
        summarize_germany("B", "B2C DE→未注册税号欧盟国家", "CQ=SELLER；F非COMMINGLING_BUY；CJ仅NO和空白；BP=DE；BQ=欧盟27国排除DE/ES/FR/IT/NL/PL；CA空白；BB=GBP/EUR/SEK/PLN；B列仅校验季度。", part_b, period, rates),
        summarize_germany("C", "无效B2B DE→EU", "CQ=SELLER；F非COMMINGLING_BUY；CJ仅NO和空白；BP=DE；BQ=其他欧盟国家；AE>0；CA非空且与BQ国家前缀不符；BB=GBP/EUR/SEK/PLN；B列仅校验季度。", part_c, period, rates),
        summarize_germany("D", "德国本土B2B", "CQ=SELLER；F非COMMINGLING_BUY；CJ仅NO和空白；BP=DE；BQ=DE；CA非空且自身基本格式有效，不要求德国税号；BB=GBP/EUR/SEK/PLN；B列仅校验季度。", part_d, period, rates),
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
        "tax_country": "DE",
        "country_name": "德国",
        "vat_rate": VAT_RATE,
        "registered_vat_countries": sorted(config["registered_vat_countries"]),
        "unregistered_eu_countries": sorted(unregistered_eu),
        "rates_for_period": rates.get(period, {}),
        "exchange_rate_source": config.get("exchange_rate_source", "config.json"),
        "summary": summary,
        "currency": currency,
        "detail": detail,
        "final": [
            {"项目": "A-D命中EUR总和", "金额EUR": eur_total},
            {"项目": "税金", "公式": "A-D命中EUR总和/1.19*0.19", "金额EUR": tax, "缺少汇率行数": missing_rates},
        ],
    }
