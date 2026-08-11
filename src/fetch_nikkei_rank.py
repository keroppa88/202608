"""日経の日本株ランキングを取得して追記する（SPEC §4F）。

https://www.nikkei.com/marketdata/ranking-jp/trading-value/  売買代金
https://www.nikkei.com/marketdata/ranking-jp/access/          株価検索数

どちらも1ページに30件（全200件）が載る。指定は「1〜30位」なので
ページ送りはしない。数値は静的HTMLに入っているのでブラウザは要らない。
表示テキストに直してから抽出する（SPEC §2.2）。

    data/raw/YYYY-MM-DD/nikkei_rank_trading_value.txt  表示テキスト
    data/raw/YYYY-MM-DD/nikkei_rank_access.txt
    data/rank_trading_value.csv                        売買代金ランキング
    data/rank_access.csv                               株価検索数ランキング

使い方:
    python3 src/fetch_nikkei_rank.py
"""

import csv
import os
import sys

import nikkei_rank_text as R
from common import fetch, now_jst, report, repo_root, save_raw
from page_text import text_from_html

# 1ページぶんの件数。これを下回ったらページの作りが変わったと疑う
LIMIT = 30

RANKINGS = (
    {
        "label": "売買代金",
        "url": "https://www.nikkei.com/marketdata/ranking-jp/trading-value/",
        "raw": "nikkei_rank_trading_value.txt",
        "csv": "rank_trading_value.csv",
        "columns": ["turnover", "last", "change", "change_pct"],
    },
    {
        "label": "株価検索数",
        "url": "https://www.nikkei.com/marketdata/ranking-jp/access/",
        "raw": "nikkei_rank_access.txt",
        "csv": "rank_access.csv",
        # 指定は順位・コード・銘柄名のみ。ページに出ている現在値などは
        # 生テキストには残るが CSV には入れない
        "columns": [],
    },
)

BASE = ["trade_date", "rank", "code", "name", "market"]
KEYS = ["trade_date", "rank"]


def merge(path, header, rows):
    """同じ日付・順位は上書きし、並べ直して書き戻す。再実行しても二重にならない。"""
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[(r["trade_date"], int(r["rank"]))] = r
    for r in rows:
        existing[(str(r["trade_date"]), int(r["rank"]))] = r

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in header})


def collect(spec, root, started):
    """1つのランキングを取って書き戻す。戻り値は (成功した件数, エラー) 。"""
    try:
        html = fetch(spec["url"]).decode("utf-8", "replace")
    except Exception as e:
        return 0, ("取得", f"{spec['label']}: {str(e).splitlines()[0]}")

    text = text_from_html(html)
    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), spec["raw"]),
        text,
    )

    try:
        rows = R.parse(text, spec["columns"], limit=LIMIT)
    except Exception as e:
        return 0, ("抽出", f"{spec['label']}: {str(e).splitlines()[0]}")

    trade_date = rows[0]["trade_date"]
    print(f"{spec['label']}: {len(rows)}件（1〜{rows[-1]['rank']}位） 取引日 {trade_date}")

    # 書き込む前に検査する。ワークフローの commit は if: always() のため、
    # 書いてしまうと失敗した実行でもコミットされる
    if len(rows) < LIMIT:
        return 0, ("抽出", f"{spec['label']}: 件数が少ない（{len(rows)} / 下限 {LIMIT}）")

    header = BASE + spec["columns"] + ["fetched_at"]
    stamp = started.isoformat(timespec="seconds")
    merge(
        os.path.join(root, "data", spec["csv"]),
        header,
        [
            {
                **{k: ("" if r.get(k) is None else r.get(k, "")) for k in header[:-1]},
                "fetched_at": stamp,
            }
            for r in rows
        ],
    )
    # 取引日ごとに上書きするので、休場日に同じページを取り直しても行は増えない
    return len(rows), None


def main(argv):
    root = repo_root()
    started = now_jst()

    ok, errors = [], []
    for spec in RANKINGS:
        count, error = collect(spec, root, started)
        if error:
            errors.append(error)
        else:
            ok.extend([spec["label"]] * count)
    return report(ok, errors, "日経・日本株ランキング")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
