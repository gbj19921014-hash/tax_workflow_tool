import re

import pandas as pd

from run_workflow import EU_COUNTRIES, exchange_to_eur, is_blank


ALLOWED_CURRENCIES = ("EUR", "PLN", "SEK")
AMOUNT_COLUMN = "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL"
VAT_RATE = 0.23


def valid_polish_vat_number(value):
    if pd.isna(value):
        return False
    cleaned = re.sub(r"[\s-]", "", str(value).strip().upper())
    return bool(re.fullmatch(r"PL\d{10}", cleaned))


def summarize_poland(code, name, rule, rows, month, rates):
    rows = rows.copy()
    rows["_original_amount"] = pd.to_numeric(rows[AMOUNT_COLUMN], errors="coerce").fillna(0.0)
    rows["_eur_amount"] = [
        exchange_to_eur(amount, currency, month, rates)
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
    missing_rates = int(rows["_eur_amount"].isna().sum())
    return {
        "summary": {
            "项目": code,
            "名称": name,
            "筛选口径": rule,
            "命中行数": int(len(rows)),
            "金额列": AMOUNT_COLUMN,
            "EUR金额总和": eur_total,
            "缺少汇率行数": missing_rates,
            "税率": VAT_RATE,
            "税金EUR": round(eur_total / (1 + VAT_RATE) * VAT_RATE, 2),
        },
        "currency": currency_rows,
        "detail": rows.assign(项目=code, 项目名称=name).to_dict("records"),
    }


def build_poland_payload(input_file, month, config):
    source = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    rows = source[source["ACTIVITY_PERIOD"].eq(month)].copy()

    registered = set(config["registered_vat_countries"])
    unregistered_eu = EU_COUNTRIES - (registered & EU_COUNTRIES)
    rates = config["exchange_rates_to_eur"]

    seller = rows["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
    buyer_vat_blank = is_blank(rows["BUYER_VAT_NUMBER"])
    valid_polish_vat = rows["BUYER_VAT_NUMBER"].map(valid_polish_vat_number)
    allowed_currency = rows["TRANSACTION_CURRENCY_CODE"].isin(ALLOWED_CURRENCIES)
    vat_amount = pd.to_numeric(rows["TOTAL_ACTIVITY_VALUE_VAT_AMT"], errors="coerce")

    # Each section starts from the same untouched month dataset.
    part_1a = rows[
        seller
        & buyer_vat_blank
        & rows["SALE_DEPART_COUNTRY"].eq("PL")
        & rows["SALE_ARRIVAL_COUNTRY"].isin(unregistered_eu)
        & allowed_currency
    ]
    part_1b = rows[
        seller
        & buyer_vat_blank
        & rows["SALE_ARRIVAL_COUNTRY"].eq("PL")
        & rows["SALE_DEPART_COUNTRY"].isin(EU_COUNTRIES)
        & allowed_currency
    ]
    part_2a = rows[
        seller
        & rows["SALE_DEPART_COUNTRY"].eq("PL")
        & rows["SALE_ARRIVAL_COUNTRY"].eq("PL")
        & valid_polish_vat
        & allowed_currency
    ]
    part_3a = rows[
        seller
        & ~buyer_vat_blank
        & rows["SALE_DEPART_COUNTRY"].eq("PL")
        & vat_amount.notna()
        & vat_amount.ne(0)
        & allowed_currency
    ]

    sections = [
        summarize_poland(
            "1A",
            "PL到未注册欧盟国家 B2C 23%",
            "B=算税月；CQ=SELLER；CA=空白；BP=PL；BQ=未注册税号的欧盟国家；BB=EUR/PLN/SEK；汇总BA。",
            part_1a,
            month,
            rates,
        ),
        summarize_poland(
            "1B",
            "欧盟国家到PL B2C 23%",
            "B=算税月；CQ=SELLER；CA=空白；BQ=PL；BP=欧盟国家；BB=EUR/PLN/SEK；汇总BA。",
            part_1b,
            month,
            rates,
        ),
        summarize_poland(
            "2A",
            "波兰境内 B2B 23%",
            "B=算税月；CQ=SELLER；BP=PL；BQ=PL；CA清除空格和连字符后符合PL+10位数字；BB=EUR/PLN/SEK；汇总BA。",
            part_2a,
            month,
            rates,
        ),
        summarize_poland(
            "3A",
            "假的欧盟境内 B2B 23%",
            "B=算税月；CQ=SELLER；CA非空；BP=PL；AQ非空且不等于0；BB=EUR/PLN/SEK；汇总BA；不限制BQ。",
            part_3a,
            month,
            rates,
        ),
    ]

    summary = [section["summary"] for section in sections]
    currency = [row for section in sections for row in section["currency"]]
    detail = [row for section in sections for row in section["detail"]]
    part_3a_summary = next(row for row in summary if row["项目"] == "3A")
    part_3a_eur_total = part_3a_summary["EUR金额总和"]
    tax = round(part_3a_eur_total / (1 + VAT_RATE) * VAT_RATE, 2)

    return {
        "source_file": str(input_file),
        "activity_period": month,
        "tax_country": "PL",
        "country_name": "波兰",
        "vat_rate": VAT_RATE,
        "registered_vat_countries": sorted(registered),
        "unregistered_eu_countries": sorted(unregistered_eu),
        "rates_for_month": rates.get(month, {}),
        "exchange_rate_source": config.get("exchange_rate_source", "config.json"),
        "summary": summary,
        "currency": currency,
        "detail": detail,
        "final": [
            {"项目": "3A命中EUR总和", "金额EUR": part_3a_eur_total},
            {
                "项目": "税金",
                "公式": "3A命中EUR总和/1.23*0.23",
                "金额EUR": tax,
                "缺少汇率行数": part_3a_summary["缺少汇率行数"],
            },
        ],
    }
