"""sector_today.json の時価総額メタデータを日次計算結果に合わせる。"""

import csv
import json
import os
import sys

from common import repo_root


def main():
    root = repo_root()
    cap_path = os.path.join(root, "data", "market_cap.csv")
    json_path = os.path.join(root, "data", "sector_today.json")

    if not os.path.exists(cap_path) or not os.path.exists(json_path):
        print("market_cap.csv または sector_today.json がない", file=sys.stderr)
        return 2

    dates = []
    dynamic = 0
    fallback = 0
    with open(cap_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            source = (row.get("source") or "").strip()
            as_of = (row.get("as_of") or "").strip()[:10]
            if source == "NP/EPS*close":
                dynamic += 1
                if as_of:
                    dates.append(as_of)
            elif source == "fallback":
                fallback += 1

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    target_date = str(data.get("date") or "")[:10]
    if target_date and target_date in dates:
        as_of = target_date
    elif dates:
        as_of = max(dates)
    else:
        as_of = data.get("marketCapAsOf") or ""

    data["marketCapAsOf"] = as_of
    data["marketCapMethod"] = "NP/EPS × latest close"
    data["marketCapDynamic"] = dynamic
    data["marketCapFallback"] = fallback

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"時価総額メタデータ更新: as_of={as_of or '-'} "
        f"dynamic={dynamic} fallback={fallback}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
