import json
from pathlib import Path

import pandas as pd

from build_workbook import build_workbook
from france_workflow import build_france_payload
from germany_workflow import build_germany_payload
from netherlands_workflow import build_netherlands_payload
from poland_workflow import build_poland_payload
from run_workflow import build_payload as build_italy_payload
from run_workflow import clean_json_value
from spain_workflow import build_spain_payload
from uk_workflow import build_uk_payload


COUNTRY_NAMES = {"IT": "意大利", "PL": "波兰", "DE": "德国", "FR": "法国", "NL": "荷兰", "ES": "西班牙", "GB": "英国"}


def build_country_payload(input_file, month, country, config):
    country = country.strip().upper()
    if country == "IT":
        country_config = dict(config)
        country_config["tax_country"] = "IT"
        payload = build_italy_payload(input_file, month, country_config)
        payload["country_name"] = COUNTRY_NAMES[country]
        payload["vat_rate"] = country_config["vat_rate"]
        for row in payload["summary"]:
            row["项目"] = row.pop("A项")
            row["税率"] = country_config["vat_rate"]
            row["税金EUR"] = round(
                row["EUR金额总和"] / (1 + country_config["vat_rate"]) * country_config["vat_rate"],
                2,
            )
        for row in payload["currency"]:
            row["项目"] = row.pop("A项")
        for row in payload["detail"]:
            row["项目"] = row.pop("A项")
            row["项目名称"] = row.pop("A项名称")
        return payload
    if country == "PL":
        return build_poland_payload(input_file, month, config)
    if country == "DE":
        return build_germany_payload(input_file, month, config)
    if country == "FR":
        return build_france_payload(input_file, month, config)
    if country == "NL":
        return build_netherlands_payload(input_file, month, config)
    if country == "ES":
        return build_spain_payload(input_file, month, config)
    if country == "GB":
        return build_uk_payload(input_file, month, config)
    raise ValueError(f"暂不支持国家：{country}")


def write_outputs(payload, output_root):
    country = payload["tax_country"]
    month = payload["activity_period"]
    out_dir = Path(output_root) / country / month
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = clean_json_value(payload)
    json_path = out_dir / "workflow_result.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    pd.DataFrame(payload["summary"]).to_csv(
        out_dir / "工作流汇总.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(payload["currency"]).to_csv(
        out_dir / "币种汇总.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(payload["final"]).to_csv(
        out_dir / "最终税金.csv", index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(payload["detail"]).to_csv(
        out_dir / "命中明细.csv", index=False, encoding="utf-8-sig"
    )

    country_name = payload.get("country_name", country)
    xlsx_path = build_workbook(
        payload,
        out_dir / f"{country_name}税务工作流输出_{month}.xlsx",
    )
    return {"output_dir": out_dir, "json_path": json_path, "xlsx_path": xlsx_path}
