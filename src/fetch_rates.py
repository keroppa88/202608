"""国債利回り・国債先物・政策金利を取得して1つのファイルに追記する（SPEC §4H）。

https://www.smbcnikko.co.jp/market/interest/

このページ1本にまとめてある。ここに無いものは取らない。

    国債利回り（終値）    24本   日米欧亜アフリカ中南米
    国債先物（15分遅れ）   1本   日本 長期国債先物
    政策金利              4本   日本2・米国・ユーロ

**終値のみで四本値は無い。** 金利は日々の値だけを記録する。

ブラウザで開いて画面の文字を丸ごと取る（SPEC §2.2）。
描画を待つだけで、語や正規表現で待ち合わせることはしない。
取れたかどうかは項目数で判断する。

    data/raw/YYYY-MM-DD/rates.txt   表示テキスト
    data/rates.csv                  利回り・政策金利

使い方:
    python3 src/fetch_rates.py
"""

import csv
import os
import sys

import rates_text as R
from common import now_jst, report, repo_root, save_raw
from page_text import capture

URL = "https://www.smbcnikko.co.jp/market/interest/"

HEADER = [
    "trade_date",
    "group",
    "name",
    "value",
    "unit",
    "change",
    "updated",
    "fetched_at",
]

KEYS = ["trade_date", "group", "name"]

# 節ごとの下限。これを下回ったらページの作りが変わったと疑う（実測 24 / 1 / 4）
MIN_ROWS = {"国債利回り": 18, "国債先物": 1, "政策金利": 3}


def dump(text):
    """失敗したときに、画面に出ていた文字を丸ごと出す。

    どこが表かをこちらで決めつけると、見当違いの場所を切り出して
    何も分からずに終わる。全部出す。
    """
    print(f"--- 画面に出ていた文字（全部）---\n{text}\n--- ここまで ---")


def merge(path, rows):
    """同じ取引日・項目は上書きし、並べ直して書き戻す。再実行しても二重にならない。"""
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
        return report([], [("取得", str(e).splitlines()[0])], "金利")

    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), "rates.txt"),
        text,
    )

    try:
        rows = R.parse(text, today=started.date())
    except Exception as e:
        dump(text)
        return report([], [("抽出", str(e).splitlines()[0])], "金利")

    counts = {}
    for r in rows:
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    print(f"{len(rows)}項目  " + " / ".join(f"{k} {v}" for k, v in counts.items()))

    # 書き込む前に検査する。ワークフローの commit は if: always()
    short = [
        f"{g}が少ない（{counts.get(g, 0)} / 下限 {n}）"
        for g, n in MIN_ROWS.items()
        if counts.get(g, 0) < n
    ]
    if short:
        dump(text)
        return report([], [("抽出", "、".join(short))], "金利")

    stamp = started.isoformat(timespec="seconds")
    merge(
        os.path.join(root, "data", "rates.csv"),
        [
            {
                "trade_date": r["trade_date"],
                "group": r["group"],
                "name": r["name"],
                "value": r["value"],
                "unit": r["unit"],
                "change": "" if r["change"] is None else r["change"],
                "updated": r["updated"],
                "fetched_at": stamp,
            }
            for r in rows
        ],
    )
    # 項目ごとに取引日が違う。ページに出ている日付をそのまま使うので、
    # 休場で日付が変わらなければ同じ行を上書きするだけになる
    print(f"記録: {len(rows)}項目")
    return report([r["name"] for r in rows], [], "金利")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
