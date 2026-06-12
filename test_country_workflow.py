import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from workflow_service import build_country_payload, write_outputs


PROJECT_ROOT = Path(__file__).resolve().parent


class CountryWorkflowIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PROJECT_ROOT / "config.json").read_text(encoding="utf-8"))

    def assert_detail_matches_csv(self, workbook, output_dir):
        csv_columns = list(pd.read_csv(output_dir / "命中明细.csv", nrows=0).columns)
        sheet = workbook["命中明细"]
        excel_columns = [sheet.cell(1, column).value for column in range(1, sheet.max_column + 1)]
        self.assertEqual(excel_columns, csv_columns)

    def test_italy_april_regression_and_workbook(self):
        input_file = Path("/Users/dlab/Downloads/54961020579.csv")
        if not input_file.exists():
            self.skipTest("意大利回归 CSV 不存在")

        payload = build_country_payload(input_file, "2026-APR", "IT", self.config)
        self.assertEqual([row["命中行数"] for row in payload["summary"]], [3, 0, 0])
        self.assertEqual(payload["final"][0]["金额EUR"], 294.68)
        self.assertEqual(payload["final"][1]["金额EUR"], 53.14)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_outputs(payload, temp_dir)
            workbook = load_workbook(paths["xlsx_path"], data_only=False)
            self.assertEqual(workbook.sheetnames, ["最终输出", "命中明细"])
            self.assertEqual(workbook["最终输出"]["A1"].value, "意大利税务工作流输出")
            self.assert_detail_matches_csv(workbook, paths["output_dir"])

    def test_poland_february_regression_and_workbook(self):
        input_file = Path("/Users/dlab/Downloads/54849020552.csv")
        if not input_file.exists():
            self.skipTest("波兰回归 CSV 不存在")

        config = json.loads(json.dumps(self.config))
        config["exchange_rates_to_eur"]["2026-FEB"] = {
            "EUR": 1.0,
            "PLN": 0.23705895,
            "SEK": 0.0940284,
            "GBP": 1.14900927,
        }
        config["exchange_rate_source"] = "ECB月平均 2026-02"
        payload = build_country_payload(input_file, "2026-FEB", "PL", config)
        self.assertEqual([row["命中行数"] for row in payload["summary"]], [0, 0, 9, 10])
        self.assertEqual(payload["final"][0]["项目"], "3A命中EUR总和")
        self.assertEqual(payload["final"][0]["金额EUR"], 82.3)
        self.assertEqual(payload["final"][1]["公式"], "3A命中EUR总和/1.23*0.23")
        self.assertEqual(payload["final"][1]["金额EUR"], 15.39)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_outputs(payload, temp_dir)
            workbook = load_workbook(paths["xlsx_path"], data_only=False)
            self.assertEqual(workbook.sheetnames, ["最终输出", "命中明细"])
            self.assertEqual(workbook["最终输出"]["A1"].value, "波兰税务工作流输出")
            self.assert_detail_matches_csv(workbook, paths["output_dir"])

    def test_germany_q1_regression_and_workbook(self):
        input_file = Path("/Users/dlab/Desktop/新建文件夹/55149020613.csv")
        if not input_file.exists():
            self.skipTest("德国回归 CSV 不存在")

        config = json.loads(json.dumps(self.config))
        config["exchange_rates_to_eur"]["2026-Q1"] = {
            "EUR": 1.0,
            "PLN": None,
            "SEK": None,
            "GBP": None,
        }
        payload = build_country_payload(input_file, "2026-Q1", "DE", config)
        self.assertEqual([row["命中行数"] for row in payload["summary"]], [5, 0, 13, 230])
        self.assertEqual(
            [row["EUR金额总和"] for row in payload["summary"]],
            [70.57, 0.0, 1644.98, 20259.81],
        )
        self.assertEqual(payload["final"][0]["金额EUR"], 21975.36)
        self.assertEqual(payload["final"][1]["公式"], "A-D命中EUR总和/1.19*0.19")
        self.assertEqual(payload["final"][1]["金额EUR"], 3508.67)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_outputs(payload, temp_dir)
            workbook = load_workbook(paths["xlsx_path"], data_only=False)
            self.assertEqual(workbook.sheetnames, ["最终输出", "命中明细"])
            self.assertEqual(workbook["最终输出"]["A1"].value, "德国税务工作流输出")
            self.assertEqual(workbook["最终输出"]["A3"].value, "算税期间")
            self.assert_detail_matches_csv(workbook, paths["output_dir"])

    def test_germany_q3_manual_review_row_is_included_and_highlighted(self):
        input_file = Path("/Users/dlab/Downloads/7-9月德国税金订单，销售额10310.89.xlsx")
        if not input_file.exists():
            self.skipTest("德国Q3核对文件不存在")

        sheets = ["A部分B2C之EU-DE", "C部分B2B之DE-EU", "D部分本土B2B"]
        source = pd.concat(
            [pd.read_excel(input_file, sheet_name=sheet, dtype=str) for sheet in sheets],
            ignore_index=True,
        )
        config = json.loads(json.dumps(self.config))
        config["exchange_rates_to_eur"]["2025-Q3"] = {
            "EUR": 1.0,
            "PLN": None,
            "SEK": None,
            "GBP": None,
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "germany-q3.csv"
            source.to_csv(csv_path, index=False, encoding="utf-8-sig")
            payload = build_country_payload(csv_path, "2025-Q3", "DE", config)
            self.assertEqual([row["命中行数"] for row in payload["summary"]], [23, 0, 8, 163])
            self.assertEqual(payload["final"][0]["金额EUR"], 10310.89)
            self.assertEqual(payload["final"][1]["金额EUR"], 1646.28)

            review_rows = [row for row in payload["detail"] if row.get("人工确认提示")]
            self.assertEqual(len(review_rows), 1)
            self.assertEqual(review_rows[0]["BUYER_VAT_NUMBER"], "ESB40654055")
            self.assertEqual(float(review_rows[0]["TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL"]), 249.99)

            paths = write_outputs(payload, temp_dir)
            workbook = load_workbook(paths["xlsx_path"], data_only=False)
            detail_sheet = workbook["命中明细"]
            headers = [detail_sheet.cell(1, column).value for column in range(1, detail_sheet.max_column + 1)]
            review_column = headers.index("人工确认提示") + 1
            highlighted = [
                row_index
                for row_index in range(2, detail_sheet.max_row + 1)
                if detail_sheet.cell(row_index, review_column).value
            ]
            self.assertEqual(len(highlighted), 1)
            self.assertEqual(detail_sheet.cell(highlighted[0], 1).fill.fgColor.rgb, "00FFF2CC")
            self.assert_detail_matches_csv(workbook, paths["output_dir"])


if __name__ == "__main__":
    unittest.main()
