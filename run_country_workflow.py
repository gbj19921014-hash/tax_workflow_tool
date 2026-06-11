#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from exchange_rates import fetch_ecb_period_rates_to_eur
from workflow_service import build_country_payload, write_outputs


def main():
    parser = argparse.ArgumentParser(description="按国家运行已确认的税务工作流。")
    parser.add_argument("--input", required=True, help="Amazon VAT CSV 文件路径")
    parser.add_argument("--month", required=True, help="算税期间，例如 2026-APR 或 2026-Q1")
    parser.add_argument("--country", required=True, choices=["IT", "PL", "DE"], help="算税国家")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "config.json"),
        help="配置文件路径",
    )
    parser.add_argument("--out", default="outputs/country_workflow", help="统一输出根目录")
    parser.add_argument("--ecb-monthly", action="store_true", help="获取指定月份的 ECB 月平均汇率")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if args.ecb_monthly:
        rate_data = fetch_ecb_period_rates_to_eur(args.month)
        config["exchange_rates_to_eur"][args.month] = rate_data["rates"]
        config["exchange_rate_source"] = f'{rate_data["source"]} {rate_data["date_range"]}'

    payload = build_country_payload(Path(args.input), args.month, args.country, config)
    paths = write_outputs(payload, args.out)
    for row in payload["summary"]:
        print(f'{row["项目"]}: {row["命中行数"]}行, {row["EUR金额总和"]:.2f} EUR')
    print(f'合计: {payload["final"][0]["金额EUR"]:.2f} EUR')
    print(f'税金: {payload["final"][1]["金额EUR"]:.2f} EUR')
    print(paths["xlsx_path"])


if __name__ == "__main__":
    main()
