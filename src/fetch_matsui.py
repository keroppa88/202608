"""松井証券の「投資指標(松井証券店内)」を取得して1つのファイルに追記する（SPEC §4G）。

https://www.matsui.co.jp/market/stock/netstock-info/

市場別株式売買代金・先導株比率・信用残速報・新規/返済申込速報・先物指標を、
松井証券の店内データとして取る。

ログインなしで見えるのは**前営業日更新分**。ページに出ている日付
（例「8/7(金)」）の数値として記録する。

数値は後から流し込まれる（Rtoaster）ので、**ブラウザで開いて画面の文字を
丸ごと取る**（CLAUDE.md / SPEC §2.2）。語や形で待ち合わせることはしない。
取れた全文をそのまま保存し、項目数が下限を下回ったら失敗とする（SPEC §2.4）。

    data/raw/YYYY-MM-DD/matsui.txt   表示テキスト
    data/matsui.csv                  指標

使い方:
    python3 src/fetch_matsui.py
"""

import csv
import os
import sys

import matsui_text as M
from common import now_jst, report, repo_root, save_raw
from page_text import capture

URL = "https://www.matsui.co.jp/market/stock/netstock-info/"

HEADER = [
    "trade_date",
    "group",
    "section",
    "item",
    "column",
    "value",
    "unit",
    "note",
    "fetched_at",
]

KEYS = ["trade_date", "group", "section", "item", "column"]

# 取れた項目がこれを下回ったら、ページの作りが変わったと疑う（実測30項目）
MIN_ROWS = 25


def merge(path, rows):
    """同じ項目は上書きし、並べ直して書き戻す。再実行しても二重にならない。"""
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

    try:
        text = capture(URL)
    except Exception as e:
        return report([], [("取得", str(e).splitlines()[0])], "松井証券・投資指標")

    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), "matsui.txt"),
        text,
    )

    try:
        rows = M.parse(text, today=started.date())
    except Exception as e:
        return report([], [("抽出", str(e).splitlines()[0])], "松井証券・投資指標")

    trade_date = rows[0]["trade_date"]
    print(f"取引日 {trade_date} / {len(rows)}項目")
    for g in dict.fromkeys(r["group"] for r in rows):
        print(f"  {g}: {sum(1 for r in rows if r['group'] == g)}項目")

    # 書き込む前に検査する。ワークフローの commit は if: always() のため、
    # 書いてしまうと失敗した実行でもコミットされる
    if len(rows) < MIN_ROWS:
        return report(
            [],
            [("抽出", f"項目が少ない（{len(rows)} / 下限 {MIN_ROWS}）。ページの作りが変わった可能性")],
            "松井証券・投資指標",
        )

    stamp = started.isoformat(timespec="seconds")
    merge(
        os.path.join(root, "data", "matsui.csv"),
        [
            {
                "trade_date": r["trade_date"],
                "group": r["group"],
                "section": r["section"],
                "item": r["item"],
                "column": r["column"],
                "value": "" if r["value"] is None else r["value"],
                "unit": r["unit"],
                "note": r["note"],
                "fetched_at": stamp,
            }
            for r in rows
        ],
    )
    # ページの日付が変わらない限り同じ行を上書きするだけなので、
    # 休場日に架空の値が増えることはない
    print(f"記録: {trade_date} に {len(rows)}項目")
    return report([r["item"] for r in rows], [], "松井証券・投資指標")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
