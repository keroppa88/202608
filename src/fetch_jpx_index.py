"""JPX の株価指数ページを開き、表示テキストを保存して指数値を取り出す（SPEC §4D）。

https://www.jpx.co.jp/markets/indices/realvalues/01.html

数値は JavaScript で描画されるため、静的HTMLには入っていない。
ブラウザで開いて画面に見えている文字を取る。
robots.txt は `Disallow:`（空）で、全パスが許可されている。

    data/raw/YYYY-MM-DD/jpx_realvalues.txt   表示テキスト
    data/jpx_index.csv                       指数値

前提:
    pip install playwright
    playwright install chromium

使い方:
    python3 src/fetch_jpx_index.py
"""

import csv
import os
import sys

import jpx_index_text as J
from common import now_jst, report, repo_root, save_raw
from page_text import browser_session

URL = "https://www.jpx.co.jp/markets/indices/realvalues/01.html"

HEADER = [
    "trade_date",
    "name",
    "open",
    "high",
    "low",
    "close",
    "change",
    "change_pct",
    "fetched_at",
]


def merge(path, rows):
    """(trade_date, name) をキーに追記する。再実行しても二重にならない。"""
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[(r["trade_date"], r["name"])] = r
    for r in rows:
        existing[(str(r["trade_date"]), r["name"])] = r

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in HEADER})


def main(argv):
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            "playwright が入っていない。\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    root = repo_root()
    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    try:
        with browser_session() as read:
            text = read(URL)
    except Exception as e:
        return report([], [("JPX 指数ページ", str(e).splitlines()[0])], "JPX指数取得")

    path = os.path.join(raw_dir, "jpx_realvalues.txt")
    save_raw(path, text)
    print(f"OK   取得  {len(text):,}文字 / {text.count(chr(10)) + 1}行 "
          f"-> {os.path.relpath(path, root)}")

    try:
        rows, skipped = J.parse(text)
    except Exception as e:
        return report([], [("抽出", str(e).splitlines()[0])], "JPX指数取得")

    # ページは「現在値」を出しており、大引け後に取れば当日の終値にあたる。
    # 日付はページ側に出ないため、実行日（JST）を取引日として扱う。
    trade_date = started.strftime("%Y-%m-%d")
    stamp = started.isoformat(timespec="seconds")
    merge(
        os.path.join(root, "data", "jpx_index.csv"),
        [
            {
                "trade_date": trade_date,
                "name": r["name"],
                "open": "" if r["open"] is None else r["open"],
                "high": "" if r["high"] is None else r["high"],
                "low": "" if r["low"] is None else r["low"],
                "close": r["close"],
                "change": "" if r["change"] is None else r["change"],
                "change_pct": "" if r["change_pct"] is None else r["change_pct"],
                "fetched_at": stamp,
            }
            for r in rows
        ],
    )

    print(f"抽出: {len(rows)}指数" + (f" / 名前や値が出ていない {skipped}行を除外" if skipped else ""))
    # 除外が多いときは描画待ちが足りていない可能性がある
    errors = []
    if skipped > len(rows) * 0.2:
        errors.append(("抽出", f"除外が多すぎる（{skipped}行 / 取得 {len(rows)}指数）"))
    return report([r["name"] for r in rows], errors, "JPX指数取得")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
