import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.build_dynamic_series import build


class DynamicSeriesTest(unittest.TestCase):
    def write_csv(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    def test_builds_full_history_per_series_and_keeps_latest_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            out = data / "dynamic"
            self.write_csv(data / "overseas_2025.csv", [
                {"trade_date": "2025-12-30", "symbol": "^TEST", "close": "90"},
            ])
            self.write_csv(data / "overseas_2026.csv", [
                {"trade_date": "2026-01-05", "symbol": "^TEST", "close": "100"},
                {"trade_date": "2026-01-05", "symbol": "^TEST", "close": "101"},
            ])

            manifest = build(data, out)
            item = manifest["series"]["yahoo:^TEST"]
            self.assertEqual(item["first"], "2025-12-30")
            self.assertEqual(item["last"], "2026-01-05")
            self.assertEqual(item["count"], 2)
            with (root / item["path"]).open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [
                {"date": "2025-12-30", "close": "90"},
                {"date": "2026-01-05", "close": "101"},
            ])
            saved = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, manifest)


if __name__ == "__main__":
    unittest.main()
