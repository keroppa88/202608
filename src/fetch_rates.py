"""国債利回りと政策金利を取得して1つのファイルに追記する（SPEC §4H）。

    SBI     日本・米国の国債（＋独・豪の10年、長期国債先物）
    楽天     その他の国の10年国債
    楽天     各国の政策金利

いずれも数値が素のHTMLに入っていない。ブラウザで開き、値が入るまで待つ。
表示テキストに直してから抽出する（SPEC §2.2）。

**終値のみで四本値は無い。** 金利は日々の値だけを記録する。

    data/raw/YYYY-MM-DD/rates_*.txt   表示テキスト
    data/rates.csv                    利回り・政策金利

使い方:
    python3 src/fetch_rates.py
"""

import csv
import os
import sys

import rates_text as R
from common import now_jst, report, repo_root, save_raw
from page_text import browser_session

SBI_BOND = (
    "https://www.sbisec.co.jp/ETGate/?OutSide=on&getFlg=on"
    "&_ControlID=WPLETmgR001Control&_PageID=WPLETmgR001Mdtl20"
    "&_ActionID=DefaultAID&_DataStoreID=DSWPLETmgR001Control"
    "&burl=iris_index&cat1=market&cat2=index&dir=tl1-idx%7Ctl2-bond&file=index.html"
)
RAKUTEN_BOND = "https://www.rakuten-sec.co.jp/web/market/data/bond_top.html"
RAKUTEN_RATE = "https://www.rakuten-sec.co.jp/web/market/data/interest_top.html"

# 楽天の債券表のうち、SBI と重なるもの。日本と米国は SBI を採る。
# ドイツも SBI の「独国債10年」と同じ（実測 3.201 と 3.200）
RAKUTEN_SKIP = ("日本", "米国", "ドイツ")

SOURCES = (
    {
        "key": "sbi_bond",
        "label": "SBI・債券",
        "url": SBI_BOND,
        "group": "国債",
        "source": "sbi",
        # 項目名ごと後から入るので語で待てる
        "wait": {"wait_text": "日本国債10年"},
        "parse": R.bonds_sbi,
        "min_rows": 12,
    },
    {
        "key": "rakuten_bond",
        "label": "楽天・債券",
        "url": RAKUTEN_BOND,
        "group": "国債",
        "source": "rakuten",
        # 項目名は素のHTMLにもある。値が入るまで待つ
        "wait": {"wait_regex": r"日本国債10年\s*[\d]"},
        "parse": R.bonds_rakuten,
        "min_rows": 10,
    },
    {
        "key": "rakuten_rate",
        "label": "楽天・政策金利",
        "url": RAKUTEN_RATE,
        "group": "政策金利",
        "source": "rakuten",
        "wait": {"wait_regex": r"無担保コール翌日物\s*[\d]"},
        "parse": R.policy_rates,
        "min_rows": 12,
    },
)

HEADER = [
    "trade_date",
    "group",
    "name",
    "value",
    "change",
    "change_pct",
    "source",
    "updated",
    "fetched_at",
]

KEYS = ["trade_date", "group", "name"]


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
    stamp = started.isoformat(timespec="seconds")
    day = started.strftime("%Y-%m-%d")
    trade_date = started.date().isoformat()

    collected, errors = [], []

    for spec in SOURCES:
        try:
            # ページごとに待ち方が違うのでブラウザは都度立ち上げる
            with browser_session(**spec["wait"]) as read:
                text = read(spec["url"])
        except Exception as e:
            errors.append(("取得", f"{spec['label']}: {str(e).splitlines()[0]}"))
            continue

        save_raw(
            os.path.join(root, "data", "raw", day, f"rates_{spec['key']}.txt"), text
        )

        try:
            rows = spec["parse"](text)
        except Exception as e:
            errors.append(("抽出", f"{spec['label']}: {str(e).splitlines()[0]}"))
            continue

        if spec["source"] == "rakuten" and spec["group"] == "国債":
            rows = [r for r in rows if not r["name"].startswith(RAKUTEN_SKIP)]

        # 値が1つも入っていなければ、待ち切れずに空の表を持ち帰っている
        filled = sum(1 for r in rows if r["value"] is not None)
        print(f"{spec['label']}: {len(rows)}項目（値あり {filled}）")
        if len(rows) < spec["min_rows"] or filled == 0:
            errors.append(
                (
                    "抽出",
                    f"{spec['label']}: 項目が足りない"
                    f"（{len(rows)} / 下限 {spec['min_rows']}、値あり {filled}）",
                )
            )
            continue

        for r in rows:
            collected.append(
                {
                    "trade_date": trade_date,
                    "group": spec["group"],
                    "name": r["name"],
                    "value": "" if r["value"] is None else r["value"],
                    "change": "" if r["change"] is None else r["change"],
                    "change_pct": "" if r["change_pct"] is None else r["change_pct"],
                    "source": spec["source"],
                    "updated": r["updated"],
                    "fetched_at": stamp,
                }
            )

    # 1つでも失敗していたら書き込まない。ワークフローの commit は if: always()
    if errors:
        return report([], errors, "国債利回り・政策金利")

    merge(os.path.join(root, "data", "rates.csv"), collected)
    print(f"記録: {trade_date} に {len(collected)}項目")
    return report([r["name"] for r in collected], [], "国債利回り・政策金利")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
