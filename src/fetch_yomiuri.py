"""読売333のページを開き、表示テキストを保存して指数値を取り出す。

    https://www.yomiuri.co.jp/yomiuri333/

数値は JavaScript で描画されるため、静的HTMLには入っていない。
ブラウザで開いて画面に見えている文字を取る（CLAUDE.md）。
語や形で待ち合わせることはしない。取れたかどうかは抽出できたかで判断する。

**終値のみで四本値は無い。** 前日比も画面に出ているので一緒に残す。

    data/raw/YYYY-MM-DD/yomiuri333.txt   表示テキスト
    data/yomiuri333.csv                  指数値

使い方:
    python3 src/fetch_yomiuri.py
"""

import csv
import os
import sys

import yomiuri_text as Y
from common import now_jst, report, repo_root, save_raw
from page_text import capture

URL = "https://www.yomiuri.co.jp/yomiuri333/"

HEADER = ["trade_date", "name", "close", "change", "change_pct", "fetched_at"]
KEYS = ["trade_date", "name"]


def dump(text):
    """失敗したときに、画面に出ていた文字を丸ごと出す。

    どこが指数値かをこちらで決めつけると、見当違いの場所を切り出して
    何も分からずに終わる。全部出す。
    """
    print(f"--- 画面に出ていた文字（全部）---\n{text}\n--- ここまで ---")


def merge(path, rows):
    """同じ取引日・指数名は上書きし、並べ直して書き戻す。再実行しても二重にならない。"""
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[tuple(r[k] for k in KEYS)] = r
    for r in rows:
        existing[tuple(str(r[k]) for k in KEYS)] = r

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in HEADER})


def main(argv):
    root = repo_root()
    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    try:
        text = capture(URL)
    except Exception as e:
        return report([], [("取得", str(e).splitlines()[0])], "読売333取得")

    # 何より先に、取れた全部を保存する
    save_raw(os.path.join(raw_dir, "yomiuri333.txt"), text)
    print(f"OK   取得  {len(text):,}文字 / {text.count(chr(10)) + 1}行")

    try:
        row = Y.parse(text)
    except Exception as e:
        dump(text)
        return report([], [("抽出", str(e).splitlines()[0])], "読売333取得")

    print(f"{row['trade_date']}  {row['name']}  {row['close']}  "
          f"前日比 {row['change']} ({row['change_pct']}%)")

    merge(
        os.path.join(root, "data", "yomiuri333.csv"),
        [
            {
                "trade_date": row["trade_date"],
                "name": row["name"],
                "close": row["close"],
                "change": "" if row["change"] is None else row["change"],
                "change_pct": "" if row["change_pct"] is None else row["change_pct"],
                "fetched_at": started.isoformat(timespec="seconds"),
            }
        ],
    )
    return report([row["name"]], [], "読売333取得")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
