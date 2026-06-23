import pandas as pd

from run_workflow import exchange_to_eur, is_blank
from tax_periods import uk_quarter_periods


ALLOWED_CURRENCIES = ("EUR", "PLN", "SEK", "GBP")
AMOUNT_COLUMN = "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL"
POST_CODE_COLUMN = "ARRIVAL_POST_CODE"
VAT_RATE = 0.20


def _is_island_postcode(value):
    postcode = str(value or "").strip().upper()
    return postcode.startswith("JE") or postcode.startswith("GY")


def summarize_uk(code, name, rule, rows, period, rates, tax_rate):
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
    original_total = round(float(rows["_original_amount"].sum()), 2)
    return {
        "summary": {
            "项目": code,
            "名称": name,
            "筛选口径": rule,
            "命中行数": int(len(rows)),
            "金额列": AMOUNT_COLUMN,
            "原币金额总和": original_total,
            "EUR金额总和": eur_total,
            "缺少汇率行数": int(rows["_eur_amount"].isna().sum()),
            "税率": tax_rate,
            "税金GBP": round(original_total / (1 + tax_rate) * tax_rate, 2) if tax_rate else 0.0,
        },
        "currency": currency_rows,
        "detail": rows.assign(项目=code, 项目名称=name).to_dict("records"),
    }


def build_uk_payload(input_file, period, config):
    source = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    expected_months = uk_quarter_periods(period)
    actual_months = sorted(source["ACTIVITY_PERIOD"].dropna().str.strip().str.upper().unique())
    if set(actual_months) != set(expected_months):
        raise ValueError(
            f"CSV 的 B 列月份与英国 {period} 不一致。应包含：{'、'.join(expected_months)}；"
            f"实际包含：{'、'.join(actual_months) or '无'}。"
        )

    allowed_currency = source["TRANSACTION_CURRENCY_CODE"].isin(ALLOWED_CURRENCIES)
    gb_to_gb = source["SALE_DEPART_COUNTRY"].eq("GB") & source["SALE_ARRIVAL_COUNTRY"].eq("GB")
    buyer_vat_blank = is_blank(source["BUYER_VAT_NUMBER"])
    buyer_vat_has_value = ~buyer_vat_blank
    seller = source["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
    island_postcode = source[POST_CODE_COLUMN].map(_is_island_postcode)

    part_b = source[seller & gb_to_gb & buyer_vat_has_value & allowed_currency]
    other_orders = source[seller & gb_to_gb & buyer_vat_blank & allowed_currency]
    part_c1 = other_orders[island_postcode[other_orders.index]]
    part_c2 = other_orders[~island_postcode[other_orders.index]]

    rates = config["exchange_rates_to_eur"]
    sections = [
        summarize_uk(
            "b",
            "B2B",
            "CQ=SELLER；BP=GB；BQ=GB；CA=有数值；BA求和；按20%计算。",
            part_b,
            period,
            rates,
            VAT_RATE,
        ),
        summarize_uk(
            "c1",
            "其他订单-岛屿零税率",
            "CQ=SELLER；BP=GB；BQ=GB；CA=空白；BO邮编以JE或GY开头；零税率。",
            part_c1,
            period,
            rates,
            0.0,
        ),
        summarize_uk(
            "c2",
            "其他订单-非岛屿GB to GB",
            "CQ=SELLER；BP=GB；BQ=GB；CA=空白；BO邮编不以JE或GY开头；按20%计算。",
            part_c2,
            period,
            rates,
            VAT_RATE,
        ),
    ]
    summary = [section["summary"] for section in sections]
    currency = [row for section in sections for row in section["currency"]]
    detail = [row for section in sections for row in section["detail"]]
    taxable_total_gbp = round(summary[0]["原币金额总和"] + summary[2]["原币金额总和"], 2)
    zero_rate_total_gbp = summary[1]["原币金额总和"]
    vat_gbp = round(taxable_total_gbp / (1 + VAT_RATE) * VAT_RATE, 2)
    missing_rates = sum(row["缺少汇率行数"] for row in summary)
    return {
        "source_file": str(input_file),
        "activity_period": period,
        "activity_periods": expected_months,
        "tax_country": "GB",
        "country_name": "英国",
        "vat_rate": VAT_RATE,
        "registered_vat_countries": sorted(config["registered_vat_countries"]),
        "rates_for_period": rates.get(period, {}),
        "exchange_rate_source": config.get("exchange_rate_source", "config.json"),
        "summary": summary,
        "currency": currency,
        "detail": detail,
        "final": [
            {"项目": "零税率销售额", "金额GBP": zero_rate_total_gbp},
            {"项目": "应税命中GBP总和", "金额GBP": taxable_total_gbp},
            {"项目": "税金", "公式": "应税命中GBP总和/1.2*0.2", "金额GBP": vat_gbp, "缺少汇率行数": missing_rates},
        ],
    }
