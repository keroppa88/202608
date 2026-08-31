"""data/stocks の個別株から当日のセクター別騰落率を作る。

毎夕 chart0 からコピーした個別株 CSV と data/stock-sectors.csv を突き合わせる。
分類マスターにある銘柄だけを対象にし、各銘柄の前回終値→最新終値の騰落率を
単純平均（等ウェイト）して大分類・セクター・業種別にまとめる。

需要地域と10のオリジナル指数は寄与度を使う。
    内需指数: 強内需=1.0 / 内需=0.5
    外需指数: 強外需=1.0 / 外需=0.5
    内外均衡はどちらにも入れない。
    オリジナル指数: 大=1.0 / 中=0.7 / 小=0.5

時価総額は data/market_cap.csv をコードで突き合わせる。
騰落率の計算には使わず、各分類の合計時価総額・1社平均時価総額を表示用に集計する。

出力:
    data/sector_today.json            当日表示用
    data/sector_history.csv           日々の履歴（同日は差し替え）
    data/original_index.csv           オリジナル10指数の長期日次データ
    data/original_index_history.json  オリジナル10指数の年初来推移
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from common import repo_root
from original_indices import ORIGINAL_INDEXES, STRENGTH_WEIGHT, classify_original_indices

JST = timezone(timedelta(hours=9))
MARKET_CAP_AS_OF = "2026-08-27"
ORIGINAL_HISTORY_YEAR = 2026
ORIGINAL_LONG_MIN_COVERAGE = 0.9
MAJOR_ORDER = {
    "外需・グローバル景気": 0,
    "資源・市況": 1,
    "内需・国内景気": 2,
    "金融・金利敏感": 3,
    "ディフェンシブ・公共": 4,
}
HISTORY_LEVEL_ORDER = {"original": 0, "demand": 1, "major": 2, "sector": 3, "industry": 4}
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
ORIGINAL_INDEX_FIELDS = [
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


def load_original_memberships(path):
    """詳細分類マスターからコード別のオリジナル指数所属を作る。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("code") or "").strip().upper()
            if not code:
                continue
            row = {
                "code": code,
                "major": (r.get("major") or "").strip(),
                "sector": (r.get("sector") or "").strip(),
                "industry": (r.get("industry") or "").strip(),
                "demand": (r.get("demand") or "").strip(),
            }
            out[code] = classify_original_indices(row)
    return out


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


def load_stock_names(path):
    """コード -> 銘柄名を返す。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("code") or "").strip().upper()
            name = (r.get("name") or "").strip()
            if code:
                out[code] = name or code
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


def load_close_history(path, year=None, date_field="Date", close_field="Close", predicate=None):
    """CSVから日付 -> 終値を読む。yearを省略すると全期間を読む。"""
    out = {}
    if not os.path.exists(path):
        return out
    prefix = f"{year}-" if year is not None else ""
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if predicate is not None and not predicate(r):
                    continue
                d = (r.get(date_field) or r.get(date_field.lower()) or "").strip()[:10]
                raw = r.get(close_field)
                if raw in (None, ""):
                    raw = r.get(close_field.lower())
                if (prefix and not d.startswith(prefix)) or raw in (None, ""):
                    continue
                try:
                    close = float(str(raw).replace(",", ""))
                except ValueError:
                    continue
                if math.isfinite(close) and close > 0:
                    out[d] = close
    except (OSError, csv.Error):
        return {}
    return out


def normalized_benchmark(index_id, name, closes):
    days = sorted(closes)
    if not days:
        return None
    base = closes[days[0]]
    points = [[d, round(closes[d] / base * 100.0, 4)] for d in days]
    latest = points[-1][1]
    return {
        "id": index_id,
        "name": name,
        "baseDate": days[0],
        "latestDate": days[-1],
        "latest": latest,
        "ytd": round(latest - 100.0, 4),
        "points": points,
    }


def weighted_history_series(definition, members, closes_by_code, calendar):
    """固定構成・固定寄与度の日次騰落率を複利し、初日100の指数にする。"""
    if not calendar:
        return None
    returns_by_code = {}
    for code, _weight in members:
        closes = closes_by_code.get(code) or {}
        previous = None
        daily = {}
        for d in sorted(closes):
            close = closes[d]
            if previous is not None:
                daily[d] = close / previous - 1.0
            previous = close
        returns_by_code[code] = daily

    level = 100.0
    points = [[calendar[0], 100.0]]
    for d in calendar[1:]:
        numerator = 0.0
        denominator = 0.0
        for code, weight in members:
            daily_return = returns_by_code.get(code, {}).get(d)
            if daily_return is None:
                continue
            numerator += daily_return * weight
            denominator += weight
        if denominator:
            level *= 1.0 + numerator / denominator
        points.append([d, round(level, 4)])

    latest = points[-1][1]
    return {
        "id": definition["id"],
        "name": definition["name"],
        "memberCount": len(members),
        "baseDate": calendar[0],
        "latestDate": calendar[-1],
        "latest": latest,
        "ytd": round(latest - 100.0, 4),
        "points": points,
    }


def covered_calendar(closes_by_code, min_coverage=ORIGINAL_LONG_MIN_COVERAGE):
    """構成銘柄の一定割合が揃った最初の日から取引日を返す。"""
    if not closes_by_code:
        return []
    counts = defaultdict(int)
    for closes in closes_by_code.values():
        for trade_date in closes:
            counts[trade_date] += 1
    required = math.ceil(len(closes_by_code) * min_coverage)
    start = next((d for d in sorted(counts) if counts[d] >= required), None)
    if start is None:
        return []
    return [d for d in sorted(counts) if d >= start]


def build_original_index_history(root, classes, original_memberships, year):
    """固定構成の10指数と日経平均・TOPIXを初日100で作る。"""
    stocks_dir = os.path.join(root, "data", "stocks")
    closes_by_code = {}
    calendar_days = set()
    for item in classes:
        code = item["code"]
        closes = load_close_history(os.path.join(stocks_dir, f"{code}.csv"), year)
        if not closes:
            continue
        closes_by_code[code] = closes
        calendar_days.update(closes)
    calendar = sorted(calendar_days)
    if not calendar:
        return None

    members_by_index = defaultdict(list)
    for item in classes:
        code = item["code"]
        memberships = original_memberships.get(code) or classify_original_indices(item)
        for index_id, strength in memberships.items():
            members_by_index[index_id].append((code, STRENGTH_WEIGHT[strength]))

    indices = []
    for definition in ORIGINAL_INDEXES:
        series = weighted_history_series(
            definition, members_by_index.get(definition["id"], []), closes_by_code, calendar
        )
        if series is not None:
            indices.append(series)

    data_dir = os.path.join(root, "data")
    nikkei = load_close_history(
        os.path.join(data_dir, f"overseas_{year}.csv"), year,
        date_field="trade_date", close_field="close",
        predicate=lambda r: (r.get("symbol") or "") == "^N225" or (r.get("name") or "") == "日経平均",
    )
    # 直近の公式CSVを年初来バックフィルへ補完する（既存値は維持）。
    recent_nikkei = load_close_history(
        os.path.join(data_dir, "nikkei_ohlc.csv"), year,
        date_field="trade_date", close_field="close",
        predicate=lambda r: (r.get("name") or "") == "日経平均",
    )
    for d, close in recent_nikkei.items():
        nikkei.setdefault(d, close)
    topix = load_close_history(
        os.path.join(data_dir, "jpx_index.csv"), year,
        date_field="trade_date", close_field="close",
        predicate=lambda r: (r.get("name") or "") == "TOPIX",
    )
    benchmarks = [
        normalized_benchmark("nikkei", "日経平均", nikkei),
        normalized_benchmark("topix", "TOPIX", topix),
    ]
    return {
        "year": year,
        "baseDate": calendar[0],
        "latestDate": calendar[-1],
        "method": "fixed_constituents_daily_weighted_return_compounded_base_100",
        "weightMethod": "large_1_medium_0.7_small_0.5",
        "indices": indices,
        "benchmarks": [item for item in benchmarks if item is not None],
        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
    }


def build_original_index_long_history(root, classes, original_memberships):
    """固定構成の10指数を、個別株CSVにある全期間について算出する。"""
    stocks_dir = os.path.join(root, "data", "stocks")
    closes_by_code = {}
    for item in classes:
        code = item["code"]
        closes = load_close_history(os.path.join(stocks_dir, f"{code}.csv"))
        if not closes:
            continue
        closes_by_code[code] = closes
    calendar = covered_calendar(closes_by_code)
    if not calendar:
        return None

    members_by_index = defaultdict(list)
    for item in classes:
        code = item["code"]
        memberships = original_memberships.get(code) or classify_original_indices(item)
        for index_id, strength in memberships.items():
            members_by_index[index_id].append((code, STRENGTH_WEIGHT[strength]))

    indices = []
    for definition in ORIGINAL_INDEXES:
        series = weighted_history_series(
            definition, members_by_index.get(definition["id"], []), closes_by_code, calendar
        )
        if series is not None:
            indices.append(series)
    return {
        "baseDate": calendar[0],
        "latestDate": calendar[-1],
        "baseMemberCoverage": sum(calendar[0] in closes for closes in closes_by_code.values()),
        "sourceMemberCount": len(closes_by_code),
        "indices": indices,
    }


def write_original_index_csv(path, history, generated_at):
    """長期指数をJPX指数CSVと同じ列構成の縦持ちCSVで保存する。"""
    previous_rows = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    previous_rows[(row.get("trade_date", ""), row.get("name", ""))] = row
        except (OSError, csv.Error):
            previous_rows = {}
    rows = []
    for series in history["indices"]:
        previous = None
        for trade_date, close in series["points"]:
            change = None if previous is None else close - previous
            change_pct = None if previous in (None, 0) else change / previous * 100.0
            formatted_close = f"{close:.4f}".rstrip("0").rstrip(".")
            old = previous_rows.get((trade_date, series["name"]), {})
            row_fetched_at = old.get("fetched_at", "") if old.get("close") == formatted_close else ""
            rows.append(
                {
                    "trade_date": trade_date,
                    "name": series["name"],
                    "open": "",
                    "high": "",
                    "low": "",
                    "close": formatted_close,
                    "change": "" if change is None else f"{change:.4f}".rstrip("0").rstrip("."),
                    "change_pct": "" if change_pct is None else f"{change_pct:.4f}".rstrip("0").rstrip("."),
                    "fetched_at": row_fetched_at or generated_at,
                }
            )
            previous = close
    order = {item["name"]: item["id"] for item in ORIGINAL_INDEXES}
    rows.sort(key=lambda row: (row["trade_date"], order.get(row["name"], 99)))
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ORIGINAL_INDEX_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


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


def original_index_rows(rows):
    """10指数を大=1.0、中=0.7、小=0.5の寄与度で加重平均する。"""
    by_index = defaultdict(list)
    for stock in rows:
        memberships = stock.get("original_memberships")
        if memberships is None:
            memberships = classify_original_indices(stock)
        for index_id, strength in memberships.items():
            by_index[index_id].append((stock, strength))

    out = []
    for definition in ORIGINAL_INDEXES:
        index_id = definition["id"]
        members = by_index.get(index_id, [])
        denominator = sum(STRENGTH_WEIGHT[strength] for _, strength in members)
        if not denominator:
            continue
        numerator = sum(
            stock["change"] * STRENGTH_WEIGHT[strength]
            for stock, strength in members
        )
        breakdown = defaultdict(int)
        for _, strength in members:
            breakdown[strength] += 1
        row = {
            **definition,
            "change": round(numerator / denominator, 4),
            "count": len(members),
            "weightSum": round(denominator, 1),
            "breakdown": {key: breakdown.get(key, 0) for key in ("大", "中", "小")},
            "members": sorted(
                [
                    {
                        "code": stock["code"],
                        "name": stock.get("name") or stock["code"],
                        "strength": strength,
                        "weight": STRENGTH_WEIGHT[strength],
                    }
                    for stock, strength in members
                ],
                key=lambda member: (-member["weight"], member["code"]),
            ),
        }
        add_market_cap_summary(row, [stock for stock, _ in members])
        out.append(row)
    return out


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


def make_history_rows(date, original, demand, major, sector, industry):
    rows = []
    for r in original:
        rows.append(history_row(date, "original", r))
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


def update_history(path, date, original, demand, major, sector, industry):
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

    current = make_history_rows(date, original, demand, major, sector, industry)
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
    detail_class_path = os.path.join(root, "data", "stock-sectors-detail.csv")
    market_cap_path = os.path.join(root, "data", "market_cap.csv")
    stock_list_path = os.path.join(root, "data", "stocks", "list.csv")
    stocks_dir = os.path.join(root, "data", "stocks")
    out_path = os.path.join(root, "data", "sector_today.json")
    history_path = os.path.join(root, "data", "sector_history.csv")
    original_long_history_path = os.path.join(root, "data", "original_index.csv")
    original_history_path = os.path.join(root, "data", "original_index_history.json")

    if not os.path.exists(class_path):
        print(f"分類マスターがない: {class_path}", file=sys.stderr)
        return 2
    if not os.path.isdir(stocks_dir):
        print(f"個別株フォルダがない: {stocks_dir}", file=sys.stderr)
        return 2

    classes = load_classes(class_path)
    original_memberships = load_original_memberships(detail_class_path)
    market_caps = load_market_caps(market_cap_path)
    stock_names = load_stock_names(stock_list_path)
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
                "name": stock_names.get(c["code"], c["code"]),
                "original_memberships": original_memberships.get(c["code"]),
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
    original = original_index_rows(today)

    major.sort(key=lambda r: (MAJOR_ORDER.get(r["name"], 99), r["name"]))
    sector.sort(key=lambda r: (MAJOR_ORDER.get(r["major"], 99), r["major"], r["name"]))
    industry.sort(key=lambda r: r["name"])

    sector_names = [r["name"] for r in sector]
    if len(sector_names) != len(set(sector_names)):
        print("セクター名称の重複が残っています", file=sys.stderr)
        return 3

    history_today, history_total = update_history(
        history_path, latest_date, original, demand, major, sector, industry
    )
    original_history = build_original_index_history(
        root, classes, original_memberships, ORIGINAL_HISTORY_YEAR
    )
    if original_history is None:
        print("オリジナル指数の年初来履歴を作れませんでした", file=sys.stderr)
        return 4
    with open(original_history_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(original_history, f, ensure_ascii=False, indent=2)
        f.write("\n")
    original_long_history = build_original_index_long_history(
        root, classes, original_memberships
    )
    if original_long_history is None:
        print("オリジナル指数の長期履歴を作れませんでした", file=sys.stderr)
        return 5
    generated_at = datetime.now(JST).isoformat(timespec="seconds")
    original_long_rows = write_original_index_csv(
        original_long_history_path, original_long_history, generated_at
    )

    matched_market_cap = sum(1 for c in classes if c["code"] in market_caps)
    missing_market_cap_codes = [c["code"] for c in classes if c["code"] not in market_caps]

    doc = {
        "date": latest_date,
        "method": "equal_weight",
        "demandMethod": "strong_1_normal_0.5",
        "originalMethod": "large_1_medium_0.7_small_0.5",
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
        "originalLongHistoryFile": "data/original_index.csv",
        "originalHistoryFile": "data/original_index_history.json",
        "generatedAt": datetime.now(JST).isoformat(timespec="seconds"),
        "original": original,
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
        f"オリジナル指数 {len(original)} / 大分類 {len(major)} / "
        f"セクター {len(sector)} / 業種 {len(industry)}"
    )
    print(
        f"  時価総額: {MARKET_CAP_AS_OF} / ランキング {len(market_caps)}銘柄 / "
        f"分類一致 {matched_market_cap}/{len(classes)}銘柄"
    )
    print(f"  履歴: 当日 {history_today}行 / 累計 {history_total}行")
    print(
        f"  年初来指数: {original_history['baseDate']}=100 / "
        f"{len(original_history['indices'])}指数 / 比較 {len(original_history['benchmarks'])}指数"
    )
    print(
        f"  長期指数: {original_long_history['baseDate']}=100 / "
        f"{original_long_history['latestDate']}まで / {original_long_rows}行 / "
        f"開始時 {original_long_history['baseMemberCoverage']}/"
        f"{original_long_history['sourceMemberCount']}銘柄"
    )
    if demand:
        print("  需要地域: " + " / ".join(f"{r['name']} {r['change']:+.2f}%" for r in demand))
    if original:
        print("  オリジナル指数: " + " / ".join(f"{r['name']} {r['change']:+.2f}%" for r in original))
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
