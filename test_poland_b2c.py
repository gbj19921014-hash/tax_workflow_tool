import tempfile
import unittest
from pathlib import Path

import pandas as pd

from exchange_rates import calculate_ecb_monthly_rates_to_eur
from poland_workflow import build_poland_payload, valid_polish_vat_number


class PolandB2CTest(unittest.TestCase):
    def test_ecb_monthly_average_uses_month_observations(self):
        csv_text = "Date,PLN,SEK,GBP\n2026-02-02,4.0,10.0,0.8\n2026-02-03,5.0,12.0,1.0\n2026-03-02,8.0,16.0,2.0\n"
        result = calculate_ecb_monthly_rates_to_eur(csv_text, "2026-FEB")
        self.assertEqual(result["observation_count"], 2)
        self.assertEqual(result["rates"]["PLN"], round(1 / 4.5, 8))
        self.assertEqual(result["rates"]["SEK"], round(1 / 11.0, 8))
        self.assertEqual(result["rates"]["GBP"], round(1 / 0.9, 8))

    def test_polish_vat_number_format(self):
        self.assertTrue(valid_polish_vat_number("PL5252733130"))
        self.assertTrue(valid_polish_vat_number("PL 525-273-31-30"))
        self.assertFalse(valid_polish_vat_number("5252733130"))
        self.assertFalse(valid_polish_vat_number("PL525273313"))
        self.assertFalse(valid_polish_vat_number("DE5252733130"))

    def test_part_a_and_b_are_filtered_independently(self):
        rows = [
            {
                "ACTIVITY_PERIOD": "2026-APR",
                "TAX_COLLECTION_RESPONSIBILITY": "SELLER",
                "BUYER_VAT_NUMBER": "",
                "SALE_DEPART_COUNTRY": "PL",
                "SALE_ARRIVAL_COUNTRY": "AT",
                "TRANSACTION_CURRENCY_CODE": "EUR",
                "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL": "123.00",
            },
            {
                "ACTIVITY_PERIOD": "2026-APR",
                "TAX_COLLECTION_RESPONSIBILITY": "SELLER",
                "BUYER_VAT_NUMBER": "",
                "SALE_DEPART_COUNTRY": "DE",
                "SALE_ARRIVAL_COUNTRY": "PL",
                "TRANSACTION_CURRENCY_CODE": "EUR",
                "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL": "246.00",
            },
            {
                "ACTIVITY_PERIOD": "2026-APR",
                "TAX_COLLECTION_RESPONSIBILITY": "SELLER",
                "BUYER_VAT_NUMBER": "",
                "SALE_DEPART_COUNTRY": "PL",
                "SALE_ARRIVAL_COUNTRY": "DE",
                "TRANSACTION_CURRENCY_CODE": "EUR",
                "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL": "999.00",
            },
            {
                "ACTIVITY_PERIOD": "2026-APR",
                "TAX_COLLECTION_RESPONSIBILITY": "SELLER",
                "BUYER_VAT_NUMBER": "PL5252733130",
                "SALE_DEPART_COUNTRY": "PL",
                "SALE_ARRIVAL_COUNTRY": "PL",
                "TRANSACTION_CURRENCY_CODE": "EUR",
                "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL": "123.00",
                "TOTAL_ACTIVITY_VALUE_VAT_AMT": "23.00",
            },
            {
                "ACTIVITY_PERIOD": "2026-APR",
                "TAX_COLLECTION_RESPONSIBILITY": "SELLER",
                "BUYER_VAT_NUMBER": "PL123",
                "SALE_DEPART_COUNTRY": "PL",
                "SALE_ARRIVAL_COUNTRY": "PL",
                "TRANSACTION_CURRENCY_CODE": "EUR",
                "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL": "999.00",
                "TOTAL_ACTIVITY_VALUE_VAT_AMT": "0.00",
            },
            {
                "ACTIVITY_PERIOD": "2026-APR",
                "TAX_COLLECTION_RESPONSIBILITY": "SELLER",
                "BUYER_VAT_NUMBER": "03294470962",
                "SALE_DEPART_COUNTRY": "PL",
                "SALE_ARRIVAL_COUNTRY": "IT",
                "TRANSACTION_CURRENCY_CODE": "EUR",
                "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL": "246.00",
                "TOTAL_ACTIVITY_VALUE_VAT_AMT": "46.00",
            },
            {
                "ACTIVITY_PERIOD": "2026-APR",
                "TAX_COLLECTION_RESPONSIBILITY": "MARKETPLACE",
                "BUYER_VAT_NUMBER": "",
                "SALE_DEPART_COUNTRY": "PL",
                "SALE_ARRIVAL_COUNTRY": "AT",
                "TRANSACTION_CURRENCY_CODE": "EUR",
                "TOTAL_ACTIVITY_VALUE_AMT_VAT_INCL": "999.00",
            },
        ]
        config = {
            "registered_vat_countries": ["DE", "IT", "ES", "FR", "NL", "PL", "GB"],
            "exchange_rates_to_eur": {"2026-APR": {"EUR": 1}},
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = Path(temp_dir) / "test.csv"
            pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8-sig")
            payload = build_poland_payload(csv_path, "2026-APR", config)

        part_a, part_b, part_2a, part_3a = payload["summary"]
        self.assertEqual(part_a["命中行数"], 1)
        self.assertEqual(part_a["EUR金额总和"], 123.0)
        self.assertEqual(part_a["税金EUR"], 23.0)
        self.assertEqual(part_b["命中行数"], 1)
        self.assertEqual(part_b["EUR金额总和"], 246.0)
        self.assertEqual(part_b["税金EUR"], 46.0)
        self.assertEqual(part_2a["命中行数"], 1)
        self.assertEqual(part_2a["EUR金额总和"], 123.0)
        self.assertEqual(part_2a["税金EUR"], 23.0)
        self.assertEqual(part_3a["命中行数"], 2)
        self.assertEqual(part_3a["EUR金额总和"], 369.0)
        self.assertEqual(part_3a["税金EUR"], 69.0)
        self.assertEqual(payload["final"][0]["金额EUR"], 861.0)
        self.assertEqual(payload["final"][1]["公式"], "3A命中EUR总和/1.23*0.23")
        self.assertEqual(payload["final"][1]["金额EUR"], 69.0)


if __name__ == "__main__":
    unittest.main()
