"""CNN の Fear & Greed Index を取得して1つのファイルに追記する（SPEC §4J）。

https://edition.cnn.com/markets/fear-and-greed

**年月日と数値だけを記録する。** ページには内訳の指標や「Extreme Greed」等の
言い回しも出ているが、生テキストには残るだけで CSV には入れない。

    data/raw/YYYY-MM-DD/cnn_fear_greed.txt   表示テキスト
    data/fear_greed.csv                      日付と値

使い方:
    python3 src/fetch_fear_greed.py
"""

import csv
import os
import sys

import cnn_fng_text as F
from common import now_jst, report, repo_root, save_raw
from page_text import capture

URL = "https://edition.cnn.com/markets/fear-and-greed"

# 値が出た証拠になる語。これが出るまで待つ
MARKER = "Previous close"

HEADER = ["trade_date", "value", "fetched_at"]


def merge(path, row):
    """同じ日付は上書きする。再実行しても二重にならない。"""
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[r["trade_date"]] = r
    existing[str(row["trade_date"])] = row

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in HEADER})


def main(argv):
    root = repo_root()
    started = now_jst()

    try:
        text = capture(URL, wait_text=MARKER)
    except Exception as e:
        return report([], [("取得", str(e).splitlines()[0])], "CNN・Fear & Greed")

    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), "cnn_fear_greed.txt"),
        text,
    )

    try:
        found = F.parse(text, today=started.date())
    except Exception as e:
        return report([], [("抽出", str(e).splitlines()[0])], "CNN・Fear & Greed")

    print(f"{found['trade_date']}  {found['value']}")
    merge(
        os.path.join(root, "data", "fear_greed.csv"),
        {
            "trade_date": found["trade_date"],
            "value": found["value"],
            "fetched_at": started.isoformat(timespec="seconds"),
        },
    )
    return report([str(found["value"])], [], "CNN・Fear & Greed")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
