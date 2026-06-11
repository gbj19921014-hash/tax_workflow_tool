import tempfile
import unittest
from pathlib import Path

import pandas as pd

from desktop_app import detect_activity_periods, infer_tax_period


class ActivityPeriodDetectionTest(unittest.TestCase):
    def _write_csv(self, periods):
        temp_dir = tempfile.TemporaryDirectory()
        csv_path = Path(temp_dir.name) / "amazon-vat.csv"
        pd.DataFrame({"OTHER": range(len(periods)), "ACTIVITY_PERIOD": periods}).to_csv(
            csv_path, index=False, encoding="utf-8-sig"
        )
        self.addCleanup(temp_dir.cleanup)
        return csv_path

    def test_detects_single_month_from_activity_period(self):
        csv_path = self._write_csv(["2026-APR", "2026-APR", None])
        self.assertEqual(detect_activity_periods(csv_path), ["2026-APR"])

    def test_returns_all_distinct_valid_months_in_file_order(self):
        csv_path = self._write_csv(["2026-FEB", "2026-APR", "2026-FEB", "invalid"])
        self.assertEqual(detect_activity_periods(csv_path), ["2026-FEB", "2026-APR"])

    def test_infers_germany_natural_quarter(self):
        self.assertEqual(
            infer_tax_period("DE", ["2026-MAR", "2026-JAN", "2026-FEB"]),
            "2026-Q1",
        )
        self.assertIsNone(infer_tax_period("DE", ["2026-JAN", "2026-MAR"]))


if __name__ == "__main__":
    unittest.main()
