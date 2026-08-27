"""data/stocks の個別株から当日のセクター別騰落率を作る。

毎夕 chart0 からコピーした個別株 CSV と data/stock-sectors.csv を突き合わせる。
分類マスターにある銘柄だけを対象にし、各銘柄の前回終値→最新終値の騰落率を
単純平均（等ウェイト）して大分類・セクター・業種別にまとめる。

需要地域の合成指数だけは次の寄与度を使う。
    内需指数: 強内需=1.0 / 内需=0.5
    外需指数: 強外需=1.0 / 外需=0.5
    内外均衡はどちらにも入れない。

時価総額は data/market_cap.csv をコードで突き合わせる。
騰落率の計算には使わず、各分類の合計時価総額・1社平均時価総額を表示用に集計する。

出力:
    data/sector_today.json   当日表示用
    data/sector_history.csv 日々の履歴（同日は差し替え）
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from common import repo_root

JST = timezone(timedelta(hours=9))
MARKET_CAP_AS_OF = "2026-08-27"
MAJOR_ORDER = {
    "外需・グローバル景気": 0,
    "資源・市況": 1,
    "内需・国内景気": 2,
    "金融・金利敏感": 3,
    "ディフェンシブ・公共": 4,
}
HISTORY_LEVEL_ORDER = {"demand": 0, "major": 1, "sector": 2, "industry": 3}
HISTORY_FIELDS = [
    "date",
    "level",
    "major",
    "sector",
    "name",
    "change",
    "count",
    "weight_sum",
    "market_cap_trillion",
    "avg_market_cap_trillion",
    "market_cap_count",
]

MAJOR_SECTOR_PREFIX = {
    "外需・グローバル景気": "グローバル",
    "資源・市況": "市況",
    "内需・国内景気": "国内",
    "金融・金利敏感": "金融",
    "ディフェンシブ・公共": "ディフェンシブ",
}

SPECIAL_SECTOR_NAMES = {
    ("外需・グローバル景気", "ハイテク・コンテンツ"): "エンタメ・電子",
    ("外需・グローバル景気", "ハイテク・ヘルスケア"): "医療・画像・電子材料",
}


def normalize_sector_names(rows):
    """セクター名を中身が判別できる一意な名称にする。"""
    prepared = []
    for r in rows:
        item = dict(r)
        key = (item["major"], item["sector"])
        item["sector"] = SPECIAL_SECTOR_NAMES.get(key, item["sector"])
        prepared.append(item)

    majors_by_sector = defaultdict(set)
    for r in prepared:
        if r["sector"]:
            majors_by_sector[r["sector"]].add(r["major"])

    duplicate_names = {name for name, majors in majors_by_sector.items() if len(majors) > 1}
    for r in prepared:
        if r["sector"] in duplicate_names:
            prefix = MAJOR_SECTOR_PREFIX.get(r["major"], r["major"])
            r["sector"] = f"{prefix}{r['sector']}"

    check = defaultdict(set)
    for r in prepared:
        if r["sector"]:
            check[r["sector"]].add(r["major"])
    still_duplicate = {name for name, majors in check.items() if len(majors) > 1}
    if still_duplicate:
        for r in prepared:
            if r["sector"] in still_duplicate:
                r["sector"] = f"{r['sector']}（{MAJOR_SECTOR_PREFIX.get(r['major'], r['major'])}）"

    return prepared


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
    return normalize_sector_names(rows)


def load_market_caps(path):
    """コード -> 時価総額(百万円) を返す。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("code") or "").strip().upper()
            raw = (r.get("market_cap_million") or "").replace(",", "").strip()
            if not code or not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            if math.isfinite(value) and value > 0:
                out[code] = value
    return out


def market_cap_band(million):
    if million is None:
        return ""
    trillion = million / 1_000_000.0
    if trillion < 0.2:
        return "<0.2兆"
    if trillion < 0.5:
        return "0.2–0.5兆"
    if trillion < 1:
        return "0.5–1兆"
    if trillion < 2:
        return "1–2兆"
    if trillion < 5:
        return "2–5兆"
    if trillion < 10:
        return "5–10兆"
    return "10兆+"


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


def add_market_cap_summary(row, members):
    caps = [r["market_cap_million"] for r in members if r.get("market_cap_million") is not None]
    row["marketCapCount"] = len(caps)
    if caps:
        total_trillion = sum(caps) / 1_000_000.0
        row["marketCapTrillion"] = round(total_trillion, 4)
        row["avgMarketCapTrillion"] = round(total_trillion / len(caps), 4)
    else:
        row["marketCapTrillion"] = None
        row["avgMarketCapTrillion"] = None
    return row


def average_rows(rows, key_fn, extra_fn=None):
    """セクター・業種用。各銘柄を完全に同じ1票として単純平均する。"""
    groups = defaultdict(list)
    extras = {}
    for r in rows:
        key = key_fn(r)
        if not key or (isinstance(key, tuple) and not all(key)):
            continue
        groups[key].append(r)
        if extra_fn:
            extras[key] = extra_fn(r)

    out = []
    for key, members in groups.items():
        vals = [r["change"] for r in members]
        row = {
            "name": key[-1] if isinstance(key, tuple) else key,
            "change": round(sum(vals) / len(vals), 4),
            "count": len(vals),
        }
        add_market_cap_summary(row, members)
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
    row = {
        "name": name,
        "change": round(numerator / denominator, 4),
        "count": len(selected),
        "weightSum": round(denominator, 1),
        "breakdown": dict(by_tag),
    }
    return add_market_cap_summary(row, selected)


def history_row(date, level, row, major="", sector=""):
    return {
        "date": date,
        "level": level,
        "major": major,
        "sector": sector,
        "name": row["name"],
        "change": row["change"],
        "count": row["count"],
        "weight_sum": row.get("weightSum", ""),
        "market_cap_trillion": row.get("marketCapTrillion", ""),
        "avg_market_cap_trillion": row.get("avgMarketCapTrillion", ""),
        "market_cap_count": row.get("marketCapCount", ""),
    }


def make_history_rows(date, demand, major, sector, industry):
    rows = []
    for r in demand:
        rows.append(history_row(date, "demand", r))
    for r in major:
        rows.append(history_row(date, "major", r))
    for r in sector:
        rows.append(history_row(date, "sector", r, major=r.get("major", "")))
    for r in industry:
        rows.append(
            history_row(
                date,
                "industry",
                r,
                major=r.get("major", ""),
                sector=r.get("sector", ""),
            )
        )
    return rows


def update_history(path, date, demand, major, sector, industry):
    """履歴を蓄積する。同一日を再計算した場合はその日の行だけ全置換する。"""
    kept = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for r in csv.DictReader(f):
                    if (r.get("date") or "") != date:
                        kept.append({k: r.get(k, "") for k in HISTORY_FIELDS})
        except (OSError, csv.Error) as e:
            print(f"履歴CSV読取警告: {e}", file=sys.stderr)

    current = make_history_rows(date, demand, major, sector, industry)
    rows = kept + current
    rows.sort(
        key=lambda r: (
            r.get("date", ""),
            HISTORY_LEVEL_ORDER.get(r.get("level", ""), 99),
            MAJOR_ORDER.get(r.get("major", ""), 99),
            r.get("major", ""),
            r.get("sector", ""),
            r.get("name", ""),
        )
    )

    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return len(current), len(rows)


def main():
    root = repo_root()
    class_path = os.path.join(root, "data", "stock-sectors.csv")
    market_cap_path = os.path.join(root, "data", "market_cap.csv")
    stocks_dir = os.path.join(root, "data", "stocks")
    out_path = os.path.join(root, "data", "sector_today.json")
    history_path = os.path.join(root, "data", "sector_history.csv")

    if not os.path.exists(class_path):
        print(f"分類マスターがない: {class_path}", file=sys.stderr)
        return 2
    if not os.path.isdir(stocks_dir):
        print(f"個別株フォルダがない: {stocks_dir}", file=sys.stderr)
        return 2

    classes = load_classes(class_path)
    market_caps = load_market_caps(market_cap_path)
    observed = []
    missing_codes = []
    unreadable_codes = []

    for c in classes:
        path = os.path.join(stocks_dir, f"{c['code']}.csv")
        if not os.path.exists(path):
            missing_codes.append(c["code"])
            continue
        pair = latest_pair(path)
        if not pair:
            unreadable_codes.append(c["code"])
            continue
        prev_d, prev, d, close = pair
        cap = market_caps.get(c["code"])
        observed.append(
            {
                **c,
                "date": d,
                "prev_date": prev_d,
                "change": (close / prev - 1.0) * 100.0,
                "market_cap_million": cap,
                "market_cap_band": market_cap_band(cap),
            }
        )

    if not observed:
        print("集計できる銘柄がない", file=sys.stderr)
        return 1

    latest_date = max(r["date"] for r in observed)
    today = [r for r in observed if r["date"] == latest_date]
    stale_codes = [r["code"] for r in observed if r["date"] != latest_date]

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
    industry.sort(key=lambda r: r["name"])

    sector_names = [r["name"] for r in sector]
    if len(sector_names) != len(set(sector_names)):
        print("セクター名称の重複が残っています", file=sys.stderr)
        return 3

    history_today, history_total = update_history(
        history_path, latest_date, demand, major, sector, industry
    )

    matched_market_cap = sum(1 for c in classes if c["code"] in market_caps)
    missing_market_cap_codes = [c["code"] for c in classes if c["code"] not in market_caps]

    doc = {
        "date": latest_date,
        "method": "equal_weight",
        "demandMethod": "strong_1_normal_0.5",
        "sectorNaming": "unique_by_market_driver",
        "classified": len(classes),
        "available": len(today),
        "missingFile": len(missing_codes),
        "missingCodes": missing_codes,
        "unreadable": len(unreadable_codes),
        "unreadableCodes": unreadable_codes,
        "stale": len(stale_codes),
        "staleCodes": stale_codes,
        "marketCapAsOf": MARKET_CAP_AS_OF,
        "marketCapSourceCount": len(market_caps),
        "marketCapMatched": matched_market_cap,
        "missingMarketCapCodes": missing_market_cap_codes,
        "marketCapBands": ["<0.2兆", "0.2–0.5兆", "0.5–1兆", "1–2兆", "2–5兆", "5–10兆", "10兆+"],
        "historyFile": "data/sector_history.csv",
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
    print(
        f"  時価総額: {MARKET_CAP_AS_OF} / ランキング {len(market_caps)}銘柄 / "
        f"分類一致 {matched_market_cap}/{len(classes)}銘柄"
    )
    print(f"  履歴: 当日 {history_today}行 / 累計 {history_total}行")
    if demand:
        print("  需要地域: " + " / ".join(f"{r['name']} {r['change']:+.2f}%" for r in demand))
    if missing_market_cap_codes:
        print("  時価総額なしコード: " + " ".join(missing_market_cap_codes))
    if missing_codes or unreadable_codes or stale_codes:
        print(
            f"  除外: ファイルなし {len(missing_codes)} / 読取不可 {len(unreadable_codes)} / "
            f"最新日未到達 {len(stale_codes)}"
        )
        if missing_codes:
            print("  ファイルなしコード: " + " ".join(missing_codes))
        if unreadable_codes:
            print("  読取不可コード: " + " ".join(unreadable_codes))
        if stale_codes:
            print("  最新日未到達コード: " + " ".join(stale_codes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
