"""国債利回りと政策金利を取得して1つのファイルに追記する（SPEC §4H）。

    国債利回り  https://jp.tradingeconomics.com/bonds
                各国の10年債。36か国を採る（rates_text.COUNTRIES）

    政策金利    https://www.rakuten-sec.co.jp/web/market/data/list.html
                4件のみ。日本 無担保コール翌日物 / 日本 公定歩合 /
                アメリカ フェデラルファンド金利 / ユーロ 市場調整金利

**終値のみで四本値は無い。** 金利は日々の値だけを記録する。

どちらもブラウザで開いて画面の文字を丸ごと取り、そのまま保存してから抽出する
（CLAUDE.md）。語や形で待ち合わせることはしない。取れたかどうかは項目数で
判断する。片方が取れなくても、取れた方は保存して記録する。

    data/raw/YYYY-MM-DD/rates_bonds.txt    国債利回りの画面
    data/raw/YYYY-MM-DD/rates_policy.txt   政策金利の画面
    data/rates.csv                         利回り・政策金利

使い方:
    python3 src/fetch_rates.py
"""

import csv
import os
import sys

import rates_text as R
from common import now_jst, report, repo_root, save_raw
from page_text import browser_session

BONDS_URL = "https://jp.tradingeconomics.com/bonds"
POLICY_URL = "https://www.rakuten-sec.co.jp/web/market/data/list.html"

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

# 節ごとの下限。これを下回ったらページの作りが変わったと疑う（実測 36 / 4）
MIN_ROWS = {"国債利回り": 25, "政策金利": 3}


def dump(label, text):
    """失敗したときに、画面に出ていた文字を丸ごと出す。

    どこが表かをこちらで決めつけると、見当違いの場所を切り出して
    何も分からずに終わる。全部出す。
    """
    print(f"--- {label}: 画面に出ていた文字（全部）---\n{text}\n--- ここまで ---")


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
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    rows, errors = [], []

    # 2ページを同じブラウザで続けて開く。片方が駄目でももう片方は取る
    sources = [
        ("国債利回り", BONDS_URL, "rates_bonds.txt", R.parse_bonds),
        ("政策金利", POLICY_URL, "rates_policy.txt", R.parse_policy),
    ]

    with browser_session() as read:
        for label, url, name, parse in sources:
            try:
                text = read(url)
            except Exception as e:
                errors.append((label, str(e).splitlines()[0]))
                continue

            # 何より先に、取れた全部を保存する
            save_raw(os.path.join(raw_dir, name), text)

            try:
                got = parse(text, today=started.date())
            except Exception as e:
                dump(label, text)
                errors.append((label, str(e).splitlines()[0]))
                continue

            print(f"{label}: {len(got)}項目")
            if len(got) < MIN_ROWS[label]:
                dump(label, text)
                errors.append((label, f"項目が少ない（{len(got)} / 下限 {MIN_ROWS[label]}）"))
                continue
            rows += got

    if not rows:
        return report([], errors or [("取得", "1件も取れなかった")], "金利")

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
    return report([r["name"] for r in rows], errors, "金利")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
