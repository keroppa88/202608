"""S&P500 セクター指数を CNBC から取得して相場データに追記する（SPEC §4I）。

https://www.cnbc.com/markets/sectors/

Yahoo はこの11指数について最新の足を返さなくなった（実測で25日分の欠落）。
CNBC は同じ指数の値を1ページにまとめて出しており、値も一致するため
**同じシンボルに書き込む**。これまでの履歴がそのまま続く。

始値は出ない。高値・安値・終値が取れる。

    data/raw/YYYY-MM-DD/cnbc_sectors.txt   表示テキスト
    data/overseas_YYYY.csv                 相場データ（相場取得と同じ置き場所）

**相場取得と同じファイルを書くので、必ず同じジョブの中で順に走らせる。**
別ジョブで同時に走らせると書き込みがぶつかる。

使い方:
    python3 src/fetch_cnbc_sectors.py
"""

import os
import sys
from datetime import timedelta, timezone

import cnbc_text as C
import market_store
from common import now_jst, report, repo_root, save_raw
from page_text import capture

URL = "https://www.cnbc.com/markets/sectors/"

# 表が出た証拠になる語
MARKER = "PREVIOUS CLOSE"

# 米東部標準時。夏時間でも「その日の取引日」は変わらないので固定でよい
ET = timezone(timedelta(hours=-5))

CATEGORY = "セクター"
MIN_ROWS = 9


def main(argv):
    root = repo_root()
    started = now_jst()

    # ページに日付が出ないので、取引所のある場所の日付を使う。
    # 朝の枠（JST 07:00）は米国の引け後にあたるので、その日の取引日になる
    trade_date = started.astimezone(ET).date().isoformat()

    try:
        text = capture(URL, wait_text=MARKER)
    except Exception as e:
        return report([], [("取得", str(e).splitlines()[0])], "CNBC・セクター指数")

    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), "cnbc_sectors.txt"),
        text,
    )

    try:
        rows = C.parse(text)
    except Exception as e:
        return report([], [("抽出", str(e).splitlines()[0])], "CNBC・セクター指数")

    print(f"取引日 {trade_date} / {len(rows)}指数")
    for r in rows:
        print(f"  {r['name']:<26} {r['close']}")

    # 書き込む前に検査する。ワークフローの commit は if: always()
    if len(rows) < MIN_ROWS:
        return report(
            [],
            [("抽出", f"指数が少ない（{len(rows)} / 下限 {MIN_ROWS}）。ページの作りが変わった可能性")],
            "CNBC・セクター指数",
        )

    stamp = started.isoformat(timespec="seconds")
    market_store.merge(
        root,
        [
            {
                "trade_date": trade_date,
                "category": CATEGORY,
                "name": r["name"],
                "symbol": r["symbol"],
                "source": "cnbc",
                "open": "",  # ページに始値が出ない
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": "",
                "currency": "USD",
                "exchange": "",
                "fetched_at": stamp,
            }
            for r in rows
        ],
    )
    print(f"記録: {trade_date} に {len(rows)}指数")
    return report([r["name"] for r in rows], [], "CNBC・セクター指数")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
