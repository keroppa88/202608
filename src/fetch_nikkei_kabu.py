"""日経の国内株式指標を取得して1つのファイルに追記する（SPEC §4E）。

https://www.nikkei.com/markets/kabu/japanidx/

時価総額・株式数・PBR・PER・株式益回り・配当利回り・売買高・売買代金・
騰落銘柄数などを、プライム／スタンダード／グロースの市場別に取る。

数値は静的HTMLに入っているのでブラウザは要らない。
表示テキストに直してから抽出する（SPEC §2.2）。

    data/raw/YYYY-MM-DD/nikkei_kabu.txt   表示テキスト
    data/nikkei_kabu.csv                  指標

使い方:
    python3 src/fetch_nikkei_kabu.py
"""

import csv
import os
import sys

import nikkei_kabu_text as K
from common import fetch, now_jst, report, repo_root, save_raw
from page_text import text_from_html

URL = "https://www.nikkei.com/markets/kabu/japanidx/"

HEADER = [
    "trade_date",
    "market",
    "section",
    "item",
    "column",
    "value",
    "unit",
    "fetched_at",
]

KEYS = ["trade_date", "market", "section", "item", "column"]

# 取れた項目がこれを下回ったら、ページの作りが変わったと疑う
MIN_ROWS = 60


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
        html = fetch(URL).decode("utf-8", "replace")
    except Exception as e:
        return report([], [("取得", str(e).splitlines()[0])], "日経・国内株式指標")

    text = text_from_html(html)
    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), "nikkei_kabu.txt"),
        text,
    )

    try:
        rows = K.parse(text, today=started.date())
    except Exception as e:
        return report([], [("抽出", str(e).splitlines()[0])], "日経・国内株式指標")

    sections = {r["section"] for r in rows}
    trade_date = rows[0]["trade_date"]
    print(f"取引日 {trade_date}（{rows[0]['market']}） / {len(rows)}項目 / {len(sections)}表")
    for s in sorted(sections):
        print(f"  {s}: {sum(1 for r in rows if r['section'] == s)}項目")

    # 書き込む前に検査する。ワークフローの commit は if: always() のため、
    # 書いてしまうと失敗した実行でもコミットされる
    if len(rows) < MIN_ROWS:
        return report(
            [],
            [("抽出", f"項目が少ない（{len(rows)} / 下限 {MIN_ROWS}）。ページの作りが変わった可能性")],
            "日経・国内株式指標",
        )

    stamp = started.isoformat(timespec="seconds")
    merge(
        os.path.join(root, "data", "nikkei_kabu.csv"),
        [
            {
                "trade_date": r["trade_date"],
                "market": r["market"],
                "section": r["section"],
                "item": r["item"],
                "column": r["column"],
                "value": "" if r["value"] is None else r["value"],
                "unit": r["unit"],
                "fetched_at": stamp,
            }
            for r in rows
        ],
    )
    # 見出しの日付が変わらない限り同じ行を上書きするだけなので、
    # 休場日に架空の値が増えることはない
    print(f"記録: {trade_date} に {len(rows)}項目")
    return report([r["item"] for r in rows], [], "日経・国内株式指標")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
