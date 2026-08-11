"""相場データの置き場所（SPEC §6）。

1行 = 1銘柄の1日。銘柄が増減しても列が変わらない長形式。

**年ごとにファイルを分ける。**

    data/overseas_1999.csv
    data/overseas_2000.csv
        ⋮
    data/overseas_2026.csv    ← 毎日の取得はこれだけを書き足す

1ファイルにまとめると 1999年以降の全銘柄で 118MB になり、
GitHub が受け付ける上限（100MB）を超える。加えて、毎日の取得は
ファイル全体を書き直すため、巨大な1ファイルだと毎朝それをコミットすることになる。
年で分ければ過去の年のファイルは一度書いたら変わらない。

読むときは年をまたいで連結する。
"""

import csv
import glob
import os

HEADER = [
    "trade_date",
    "category",
    "name",
    "symbol",
    "source",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "currency",
    "exchange",
    "fetched_at",
]

KEYS = ("trade_date", "symbol")

PREFIX = "overseas_"


def path_for(root, year):
    return os.path.join(root, "data", f"{PREFIX}{year}.csv")


def all_paths(root):
    return sorted(glob.glob(os.path.join(root, "data", f"{PREFIX}*.csv")))


def _year(row):
    return str(row["trade_date"])[:4]


def merge(root, new_rows):
    """(取引日, シンボル) をキーに、年ごとのファイルへ書き込む。

    同じ日を取り直しても二重にならず、後から過去分を足しても順序が崩れない。
    戻り値は {年: 書き込んだ後の行数}。
    """
    by_year = {}
    for r in new_rows:
        by_year.setdefault(_year(r), []).append(r)

    written = {}
    for year, rows in sorted(by_year.items()):
        path = path_for(root, year)
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
        written[year] = len(existing)
    return written


def read_all(root):
    """全部の年を読んで1つのリストにする。"""
    rows = []
    for path in all_paths(root):
        with open(path, encoding="utf-8", newline="") as f:
            rows.extend(csv.DictReader(f))
    return rows
