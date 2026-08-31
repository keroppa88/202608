#!/usr/bin/env python3
"""Build lightweight per-series close histories for the Dynamic chart."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "dynamic"


def add_rows(store, path: Path, key_column: str, value_column: str, prefix: str) -> None:
    if not path.exists():
        return
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            name = (row.get(key_column) or "").strip()
            date = (row.get("trade_date") or "").strip()
            value = (row.get(value_column) or "").strip()
            if not name or not date or not value:
                continue
            try:
                float(value)
            except ValueError:
                continue
            store[f"{prefix}:{name}"][date] = value


def collect_series(data_dir: Path = DATA_DIR):
    store = defaultdict(dict)
    for path in sorted(data_dir.glob("overseas_*.csv")):
        add_rows(store, path, "symbol", "close", "yahoo")
    add_rows(store, data_dir / "jpx_index.csv", "name", "close", "jpx")
    add_rows(store, data_dir / "nikkei_ohlc.csv", "name", "close", "nikkei")
    add_rows(store, data_dir / "yomiuri333.csv", "name", "close", "yomiuri")
    add_rows(store, data_dir / "ratios.csv", "name", "close", "ratio")
    add_rows(store, data_dir / "original_index.csv", "name", "close", "original")
    add_rows(store, data_dir / "rates.csv", "name", "value", "rates")
    return store


def build(data_dir: Path = DATA_DIR, output_dir: Path = OUTPUT_DIR) -> dict:
    series = collect_series(data_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    manifest = {"version": 1, "series": {}}
    for key in sorted(series):
        points = sorted(series[key].items())
        if not points:
            continue
        filename = f"{hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]}.csv"
        with (output_dir / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("date", "close"))
            writer.writerows(points)
        manifest["series"][key] = {
            "path": f"data/dynamic/{filename}",
            "first": points[0][0],
            "last": points[-1][0],
            "count": len(points),
        }

    with (output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    return manifest


if __name__ == "__main__":
    result = build()
    print(f"dynamic series: {len(result['series'])}")
