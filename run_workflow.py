#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

import pandas as pd

try:
    from build_workbook import build_workbook
except ImportError:
    build_workbook = None


EU_COUNTRIES = {
    "AT",
    "BE",
    "BG",
    "HR",
    "CY",
    "CZ",
    "DK",
    "EE",
    "FI",
    "FR",
    "DE",
    "GR",
    "HU",
    "IE",
    "IT",
    "LV",
    "LT",
    "LU",
    "MT",
    "NL",
    "PL",
    "PT",
    "RO",
    "SK",
    "SI",
    "ES",
    "SE",
}


def is_blank(series):
    return series.isna() | series.astype(str).str.strip().eq("")


def clean_tax_number(value):
    if pd.isna(value):
        return ""
    return re.sub(r"[\s-]", "", str(value).strip().upper())


def basic_tax_number_format_ok(value):
    value = clean_tax_number(value)
    return bool(re.fullmatch(r"[A-Z0-9]{5,}", value))


def has_country_prefix(country, value):
    return clean_tax_number(value).startswith(str(country).upper())


def exchange_to_eur(amount, currency, month, rates):
    currency = "" if pd.isna(currency) else str(currency).strip().upper()
    if not currency:
        return None
    if currency == "EUR":
        return float(amount)
    month_rates = rates.get(month, {})
    rate = month_rates.get(currency)
    if rate is None:
        return None
    return float(amount) * float(rate)


def summarize(code, name, rule, rows, amount_col, month, rates):
    rows = rows.copy()
    rows["_original_amount"] = pd.to_numeric(rows[amount_col], errors="coerce").fillna(0.0)
    rows["_eur_amount"] = [
        exchange_to_eur(amount, currency, month, rates)
        for amount, currency in zip(rows["_original_amount"], rows["TRANSACTION_CURRENCY_CODE"])
    ]

    currency_rows = []
    for currency in ["EUR", "PLN", "SEK", "GBP"]:
        part = rows[rows["TRANSACTION_CURRENCY_CODE"].fillna("").eq(currency)]
        original = float(part["_original_amount"].sum()) if len(part) else 0.0
        eur = part["_eur_amount"].dropna().sum() if len(part) else 0.0
        missing = int(part["_eur_amount"].isna().sum()) if len(part) else 0
        currency_rows.append(
            {
                "A项": code,
                "币种": currency,
                "行数": int(len(part)),
                "原币合计": round(original, 2),
                "折EUR金额": round(float(eur), 2),
                "缺少汇率行数": missing,
            }
        )

    eur_total = round(float(rows["_eur_amount"].dropna().sum()), 2)
    return {
        "summary": {
            "A项": code,
            "名称": name,
            "筛选口径": rule,
            "命中行数": int(len(rows)),
            "金额列": amount_col,
            "EUR金额总和": eur_total,
            "缺少汇率行数": int(rows["_eur_amount"].isna().sum()),
        },
        "currency": currency_rows,
        "detail": rows.assign(A项=code, A项名称=name).to_dict("records"),
    }


def build_payload(input_file, month, config):
    df = pd.read_csv(input_file, dtype=str, encoding="utf-8-sig")
    df = df[df["ACTIVITY_PERIOD"].eq(month)].copy()

    tax_country = config["tax_country"]
    registered = set(config["registered_vat_countries"])
    registered_eu = registered & EU_COUNTRIES
    unregistered_eu = EU_COUNTRIES - registered_eu
    rates = config["exchange_rates_to_eur"]

    seller = df["TAX_COLLECTION_RESPONSIBILITY"].eq("SELLER")
    non_commingling = ~df["TRANSACTION_TYPE"].eq("COMMINGLING_BUY")
    export_no_blank = df["EXPORT_OUTSIDE_EU"].eq("NO") | is_blank(df["EXPORT_OUTSIDE_EU"])
    ca_blank = is_blank(df["BUYER_VAT_NUMBER"])
    ca_not_blank = ~ca_blank
    vat_rate_number = pd.to_numeric(df["PRICE_OF_ITEMS_VAT_RATE_PERCENT"], errors="coerce")
    currency_b2c = df["TRANSACTION_CURRENCY_CODE"].isin(["EUR", "PLN", "SEK"])
    currency_all = df["TRANSACTION_CURRENCY_CODE"].isin(["EUR", "PLN", "SEK", "GBP"])

    a1_mask = (
        seller
        & non_commingling
        & export_no_blank
        & df["SALE_DEPART_COUNTRY"].isin(EU_COUNTRIES)
        & df["SALE_ARRIVAL_COUNTRY"].eq(tax_country)
        & ca_blank
        & currency_b2c
    )

    a2_mask = (
        seller
        & non_commingling
        & export_no_blank
        & df["SALE_DEPART_COUNTRY"].eq(tax_country)
        & df["SALE_ARRIVAL_COUNTRY"].isin(unregistered_eu)
        & ca_blank
        & currency_b2c
    )

    ca_has_country_prefix = pd.Series(
        [
            has_country_prefix(country, vat)
            for country, vat in zip(df["SALE_ARRIVAL_COUNTRY"], df["BUYER_VAT_NUMBER"])
        ],
        index=df.index,
    )
    ca_invalid_cross_border = ca_not_blank & ~ca_has_country_prefix
    a3_mask = (
        seller
        & non_commingling
        & export_no_blank
        & vat_rate_number.gt(0)
        & df["SALE_DEPART_COUNTRY"].eq(tax_country)
        & df["SALE_ARRIVAL_COUNTRY"].isin(EU_COUNTRIES - {tax_country})
        & currency_all
        & ca_invalid_cross_border
    )

    sections = [
        summarize(
            "A1",
            "EU-IT SALE_B2C_22%-B2C",
            "B=算税月；CQ=SELLER；F非COMMINGLING_BUY；CJ=NO+空白；BP=欧盟国家；BQ=算税国家；CA=空白；BB=EUR/PLN/SEK；汇总BA。",
            df[a1_mask],
            "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL",
            month,
            rates,
        ),
        summarize(
            "A2",
            "IT-EU SALE_B2C_22%-B2C",
            "B=算税月；CQ=SELLER；F非COMMINGLING_BUY；CJ=NO+空白；BP=算税国家；BQ=客户未注册税号的欧盟国家；CA=空白；BB=EUR/PLN/SEK；汇总BA。",
            df[a2_mask],
            "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL",
            month,
            rates,
        ),
        summarize(
            "A3",
            "IT-EU SALE_非B2B_22%-B2C",
            "B=算税月；CQ=SELLER；F非COMMINGLING_BUY；CJ=NO+空白；AE>0；BP=算税国家；BQ=算税国家之外的欧盟国家；CA非空且跨境VAT格式不符合；BB=EUR/PLN/SEK/GBP；汇总BA。",
            df[a3_mask],
            "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL",
            month,
            rates,
        ),
    ]

    summary = [section["summary"] for section in sections]
    currency = [row for section in sections for row in section["currency"]]
    detail = [row for section in sections for row in section["detail"]]
    eur_total = round(sum(row["EUR金额总和"] for row in summary), 2)
    tax = round(eur_total / (1 + config["vat_rate"]) * config["vat_rate"], 2)

    return {
        "source_file": str(input_file),
        "activity_period": month,
        "tax_country": tax_country,
        "registered_vat_countries": sorted(registered),
        "unregistered_eu_countries": sorted(unregistered_eu),
        "rates_for_month": rates.get(month, {}),
        "summary": summary,
        "currency": currency,
        "detail": detail,
        "final": [
            {"项目": "A1-A3命中EUR总和", "金额EUR": eur_total},
            {"项目": "税金", "公式": "命中EUR总和/1.22*0.22", "金额EUR": tax},
        ],
    }


def clean_json_value(value):
    if isinstance(value, float) and pd.isna(value):
        return None
    if value is pd.NA:
        return None
    if isinstance(value, dict):
        return {key: clean_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json_value(item) for item in value]
    return value


def main():
    parser = argparse.ArgumentParser(description="按已确认工作流计算A1-A3和税金。")
    parser.add_argument("--input", required=True, help="Amazon VAT CSV 文件路径")
    parser.add_argument("--month", required=True, help="算税月，例如 2026-MAR")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parent / "config.json"), help="配置文件路径")
    parser.add_argument("--out", default="outputs/auto_tax_workflow", help="输出文件夹")
    parser.add_argument("--no-xlsx", action="store_true", help="只输出 CSV/JSON，不生成 Excel")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_dir = Path(args.out) / args.month
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = clean_json_value(build_payload(Path(args.input), args.month, config))
    json_path = out_dir / "workflow_result.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )

    pd.DataFrame(payload["summary"]).to_csv(out_dir / "A1-A3汇总.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(payload["currency"]).to_csv(out_dir / "币种汇总.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(payload["final"]).to_csv(out_dir / "最终税金.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(payload["detail"]).to_csv(out_dir / "命中明细.csv", index=False, encoding="utf-8-sig")

    if not args.no_xlsx and build_workbook:
        xlsx_path = build_workbook(payload, out_dir / f"A1-A3未代扣代缴输出_{args.month}.xlsx")
        print(xlsx_path)

    print(json_path)
    for row in payload["summary"]:
        print(f'{row["A项"]}: {row["命中行数"]}行, {row["EUR金额总和"]:.2f} EUR')
    print(f'A1-A3合计: {payload["final"][0]["金额EUR"]:.2f} EUR')
    print(f'税金: {payload["final"][1]["金额EUR"]:.2f} EUR')


if __name__ == "__main__":
    main()
