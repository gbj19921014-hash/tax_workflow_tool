import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from workflow_service import build_country_payload, write_outputs


PROJECT_ROOT = Path(__file__).resolve().parent


class CountryWorkflowIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((PROJECT_ROOT / "config.json").read_text(encoding="utf-8"))

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
            self.assertEqual(workbook.sheetnames, ["最终输出", "筛选口径", "币种汇总", "命中明细"])
            self.assertEqual(workbook["最终输出"]["A1"].value, "意大利税务工作流输出")

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
        self.assertEqual(payload["final"][0]["金额EUR"], 130.33)
        self.assertEqual(payload["final"][1]["公式"], "3A命中EUR总和/1.23*0.23")
        self.assertEqual(payload["final"][1]["金额EUR"], 15.39)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_outputs(payload, temp_dir)
            workbook = load_workbook(paths["xlsx_path"], data_only=False)
            self.assertEqual(workbook["最终输出"]["A1"].value, "波兰税务工作流输出")
            self.assertEqual(workbook["筛选口径"]["A5"].value, "3A")

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
            self.assertEqual(workbook["最终输出"]["A1"].value, "德国税务工作流输出")
            self.assertEqual(workbook["最终输出"]["A3"].value, "算税期间")
            self.assertEqual(workbook["筛选口径"]["A5"].value, "D")


if __name__ == "__main__":
    unittest.main()
