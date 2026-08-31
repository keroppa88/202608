import csv
import json
import os
import sys
import unittest
from tempfile import TemporaryDirectory


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from original_indices import (  # noqa: E402
    ORIGINAL_INDEXES,
    STRENGTH_WEIGHT,
    classify_original_indices,
)
from calc_stock_sectors import (  # noqa: E402
    covered_calendar,
    original_index_rows,
    write_original_index_csv,
)


def load_rows():
    path = os.path.join(ROOT, "data", "stock-sectors-detail.csv")
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row["code"]: row for row in csv.DictReader(f)}


class OriginalIndexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_rows()

    def memberships(self, code):
        return classify_original_indices(self.rows[code])

    def test_defines_exactly_ten_indices_and_valid_strengths(self):
        self.assertEqual([item["id"] for item in ORIGINAL_INDEXES], list(range(1, 11)))
        for row in self.rows.values():
            memberships = classify_original_indices(row)
            self.assertTrue(memberships, row["code"])
            self.assertTrue(set(memberships).issubset(range(1, 11)))
            self.assertTrue(set(memberships.values()).issubset(STRENGTH_WEIGHT))

    def test_rental_property_and_home_sales_are_separate(self):
        self.assertEqual(self.memberships("8801").get(1), "大")
        self.assertNotIn(6, self.memberships("8801"))
        self.assertEqual(self.memberships("3288").get(6), "大")
        self.assertNotIn(1, self.memberships("3288"))
        self.assertEqual(self.memberships("1925").get(6), "大")

    def test_housing_equipment_is_large_living_expense(self):
        self.assertEqual(self.memberships("5938").get(6), "大")

    def test_luxury_and_attention_use_different_primary_indices(self):
        self.assertEqual(self.memberships("4911").get(7), "大")
        self.assertNotIn(8, self.memberships("4911"))
        self.assertEqual(self.memberships("4689").get(8), "大")
        self.assertNotIn(7, self.memberships("4689"))

    def test_overseas_strength_uses_demand_tag(self):
        self.assertEqual(self.memberships("7203").get(10), "大")
        self.assertEqual(self.memberships("7974").get(10), "中")

    def test_original_rows_expose_members_with_name_and_weight(self):
        rows = [
            {
                "code": "2222", "name": "中寄与", "change": 1.0,
                "market_cap_million": 100, "original_memberships": {1: "中"},
            },
            {
                "code": "1111", "name": "大寄与", "change": 2.0,
                "market_cap_million": 200, "original_memberships": {1: "大"},
            },
        ]
        index = original_index_rows(rows)[0]
        self.assertEqual(index["count"], len(index["members"]))
        self.assertEqual(index["members"], [
            {"code": "1111", "name": "大寄与", "strength": "大", "weight": 1.0},
            {"code": "2222", "name": "中寄与", "strength": "中", "weight": 0.7},
        ])

    def test_sector_today_members_match_displayed_counts(self):
        path = os.path.join(ROOT, "data", "sector_today.json")
        with open(path, encoding="utf-8") as f:
            today = json.load(f)
        self.assertEqual(len(today["original"]), 10)
        for index in today["original"]:
            self.assertEqual(index["count"], len(index["members"]))
            self.assertTrue(all(member["code"] and member["name"] for member in index["members"]))
            self.assertTrue(all(member["strength"] in STRENGTH_WEIGHT for member in index["members"]))
            self.assertTrue(all(member["weight"] == STRENGTH_WEIGHT[member["strength"]] for member in index["members"]))

    def test_history_is_base_100_and_has_benchmarks(self):
        path = os.path.join(ROOT, "data", "original_index_history.json")
        with open(path, encoding="utf-8") as f:
            history = json.load(f)
        self.assertEqual(history["year"], 2026)
        self.assertEqual(history["baseDate"], "2026-01-05")
        self.assertEqual(len(history["indices"]), 10)
        self.assertEqual({item["name"] for item in history["benchmarks"]}, {"日経平均", "TOPIX"})
        for item in history["indices"] + history["benchmarks"]:
            self.assertEqual(item["points"][0], ["2026-01-05", 100.0])
            self.assertEqual(item["ytd"], round(item["latest"] - 100.0, 4))
            self.assertEqual(item["points"], sorted(item["points"], key=lambda point: point[0]))

    def test_long_history_uses_index_csv_shape(self):
        history = {
            "indices": [
                {"name": "ブルジョワ地主指数", "points": [["2016-02-05", 100.0], ["2016-02-08", 101.25]]},
                {"name": "政治寄生指数", "points": [["2016-02-05", 100.0], ["2016-02-08", 99.5]]},
            ]
        }
        with TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "original_index.csv")
            count = write_original_index_csv(path, history, "2026-08-30T00:00:00+09:00")
            with open(path, encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
                self.assertEqual(list(rows[0]), [
                    "trade_date", "name", "open", "high", "low", "close",
                    "change", "change_pct", "fetched_at",
                ])
        self.assertEqual(count, 4)
        self.assertEqual(rows[0]["close"], "100")
        self.assertEqual(rows[2]["change"], "1.25")
        self.assertEqual(rows[2]["change_pct"], "1.25")

    def test_long_history_starts_after_most_members_exist(self):
        closes = {
            "a": {"2016-02-01": 1, "2016-02-05": 2, "2016-02-08": 3},
            "b": {"2016-02-05": 2, "2016-02-08": 3},
            "c": {"2016-02-05": 2, "2016-02-08": 3},
            "d": {"2016-02-05": 2, "2016-02-08": 3},
        }
        self.assertEqual(covered_calendar(closes, 0.75), ["2016-02-05", "2016-02-08"])


if __name__ == "__main__":
    unittest.main()
