import csv
import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from original_indices import (  # noqa: E402
    ORIGINAL_INDEXES,
    STRENGTH_WEIGHT,
    classify_original_indices,
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


if __name__ == "__main__":
    unittest.main()
