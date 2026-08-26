"""data/stocks の個別株から当日のセクター別騰落率を作る。

毎夕 chart0 からコピーした個別株 CSV と data/stock-sectors.csv を突き合わせる。
分類マスターにある銘柄だけを対象にし、各銘柄の前回終値→最新終値の騰落率を
単純平均（等ウェイト）して大分類・セクター・業種別にまとめる。

需要地域の合成指数だけは次の寄与度を使う。
    内需指数: 強内需=1.0 / 内需=0.5
    外需指数: 強外需=1.0 / 外需=0.5
    内外均衡はどちらにも入れない。

出力:
    data/sector_today.json

時価総額は使わない。セクター内は「構成銘柄が平均して今日は何％動いたか」を見る
等ウェイト指標である。最新日まで更新されていない銘柄は当日の集計から除外する。
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from common import repo_root

# 分類・計算式を更新したときも workflow の push トリガーで当日分を作り直す。
JST = timezone(timedelta(hours=9))
MAJOR_ORDER = {
    "外需・グローバル景気": 0,
    "資源・市況": 1,
    "内需・国内景気": 2,
    "金融・金利敏感": 3,
    "ディフェンシブ・公共": 4,
}


def load_classes(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = []
        for r in csv.DictReader(f):
            code = (r.get("code") or "").strip().upper()
            if not code:
                continue
            rows.append(
                {
                    "code": code,
                    "major": (r.get("major") or "").strip(),
                    "sector": (r.get("sector") or "").strip(),
                    "industry": (r.get("industry") or "").strip(),
                    "demand": (r.get("demand") or "").strip(),
                }
            )
    return rows


def latest_pair(path):
    """最後の2取引日の (日付, 終値) を返す。読めなければ None。"""
    last_by_date = {}
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                d = (r.get("Date") or r.get("date") or "").strip()[:10]
                raw = r.get("Close") if r.get("Close") not in (None, "") else r.get("close")
                if not d or raw in (None, ""):
                    continue
                try:
                    close = float(str(raw).replace(",", ""))
                except ValueError:
                    continue
                if not math.isfinite(close) or close <= 0:
                    continue
                last_by_date[d] = close
    except OSError:
        return None

    if len(last_by_date) < 2:
        return None
    days = sorted(last_by_date)
    prev_d, last_d = days[-2], days[-1]
    return prev_d, last_by_date[prev_d], last_d, last_by_date[last_d]


def average_rows(rows, key_fn, extra_fn=None):
    """セクター・業種用。各銘柄を完全に同じ1票として単純平均する。"""
    groups = defaultdict(list)
    extras = {}
    for r in rows:
        key = key_fn(r)
        if not key or (isinstance(key, tuple) and not all(key)):
            continue
        groups[key].append(r["change"])
        if extra_fn:
            extras[key] = extra_fn(r)

    out = []
    for key, vals in groups.items():
        row = {
            "name": key[-1] if isinstance(key, tuple) else key,
            "change": round(sum(vals) / len(vals), 4),
            "count": len(vals),
        }
        if extra_fn:
            row.update(extras[key])
        out.append(row)
    return out


def demand_index(rows, name, weights):
    """需要地域指数。強=1、通常=0.5の寄与度で加重平均する。"""
    selected = []
    numerator = 0.0
    denominator = 0.0
    by_tag = defaultdict(int)
    for r in rows:
        weight = weights.get(r["demand"])
        if weight is None:
            continue
        numerator += r["change"] * weight
        denominator += weight
        selected.append(r)
        by_tag[r["demand"]] += 1
    if not denominator:
        return None
    return {
        "name": name,
        "change": round(numerator / denominator, 4),
        "count": len(selected),
        "weightSum": round(denominator, 1),
        "breakdown": dict(by_tag),
    }


def main():
    root = repo_root()
    class_path = os.path.join(root, "data", "stock-sectors.csv")
    stocks_dir = os.path.join(root, "data", "stocks")
    out_path = os.path.join(root, "data", "sector_today.json")

    if not os.path.exists(class_path):
        print(f"分類マスターがない: {class_path}", file=sys.stderr)
        return 2
    if not os.path.isdir(stocks_dir):
        print(f"個別株フォルダがない: {stocks_dir}", file=sys.stderr)
        return 2

    classes = load_classes(class_path)
    observed = []
    missing_file = 0
    unreadable = 0

    for c in classes:
        path = os.path.join(stocks_dir, f"{c['code']}.csv")
        if not os.path.exists(path):
            missing_file += 1
            continue
        pair = latest_pair(path)
        if not pair:
            unreadable += 1
            continue
        prev_d, prev, d, close = pair
        observed.append(
            {
                **c,
                "date": d,
                "prev_date": prev_d,
                "change": (close / prev - 1.0) * 100.0,
            }
        )

    if not observed:
        print("集計できる銘柄がない", file=sys.stderr)
        return 1

    latest_date = max(r["date"] for r in observed)
    today = [r for r in observed if r["date"] == latest_date]
    stale = len(observed) - len(today)

    major = average_rows(today, lambda r: r["major"])
    sector = average_rows(
        today,
        lambda r: (r["major"], r["sector"]),
        lambda r: {"major": r["major"]},
    )
    industry = average_rows(
        today,
        lambda r: (r["major"], r["sector"], r["industry"]),
        lambda r: {"major": r["major"], "sector": r["sector"]},
    )

    demand = [
        demand_index(today, "内需", {"強内需": 1.0, "内需": 0.5}),
        demand_index(today, "外需", {"強外需": 1.0, "外需": 0.5}),
    ]
    demand = [r for r in demand if r is not None]

    major.sort(key=lambda r: (MAJOR_ORDER.get(r["name"], 99), r["name"]))
    sector.sort(key=lambda r: (MAJOR_ORDER.get(r["major"], 99), r["major"], r["name"]))
    industry.sort(
        key=lambda r: (MAJOR_ORDER.get(r["major"], 99), r["major"], r["sector"], r["name"])
    )

    doc = {
        "date": latest_date,
        "method": "equal_weight",
        "demandMethod": "strong_1_normal_0.5",
        "classified": len(classes),
        "available": len(today),
        "missingFile": missing_file,
        "unreadable": unreadable,
        "stale": stale,
        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "demand": demand,
        "major": major,
        "sector": sector,
        "industry": industry,
    }

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"セクター騰落率 {latest_date}: 使用 {len(today)}/{len(classes)}銘柄 / "
        f"大分類 {len(major)} / セクター {len(sector)} / 業種 {len(industry)}"
    )
    if demand:
        print("  需要地域: " + " / ".join(f"{r['name']} {r['change']:+.2f}%" for r in demand))
    if missing_file or unreadable or stale:
        print(
            f"  除外: ファイルなし {missing_file} / 読取不可 {unreadable} / "
            f"最新日未到達 {stale}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
