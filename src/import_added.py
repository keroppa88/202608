"""`追加/` に置いた四本値のCSVを、既存の蓄積に取り込む。

手で用意した過去分を入れるための道具。日々の取得とは関係しない。

    追加/日経平均.csv         → data/overseas_YYYY.csv（^N225）
    追加/topix.csv 他        → data/jpx_index.csv（JPXの指数名で入れる）
    追加/○○ １０年 債券利回りの過去データ.csv
                             → data/rates.csv（国債利回り）

入力の形は2つある。

  四本値（Date から始まる）

    Date,Open,High,Low,Close,Volume,TradingValue,UpLimit,LowLimit
    2026-08-10,4078.80,4111.35,4063.49,4100.61,,,,

  日付から始まるもの（債券利回り・グロース250）

    日付,終値,始値,高値,安値,変化率 %
    2026/8/14,2.878,2.876,2.881,2.842,0.14%

    日付は 2026/8/14 と 2026-08-14 のどちらもある

同じ日・同じ銘柄の行は上書きしない。取得したものを手入力で塗り替えない。

使い方:
    python3 src/import_added.py
"""

import csv
import glob
import os
import sys

import market_store
from common import now_jst, repo_root

# ファイル名 → 入れる先。JPX の指数はページに出ている名前に合わせる
TO_JPX = {
    "topix": "TOPIX",
    "topixグロース": "TOPIX グロース",
    "topixバリュー": "TOPIX バリュー",
    "東証REIT": "東証REIT指数",
    "東証REITオフィス": "東証REITオフィス指数",
    "東証REIT住宅": "東証REIT住宅指数",
    "東証REIT商業物流": "東証REIT商業・物流等指数",
    "東証グロース250": "東証グロース市場250指数",
}

# 「日付,終値,始値,高値,安値,…」の形で来るファイル。四本値として入れる
TO_JPX_JP = {
    "グロース250": "東証グロース市場250指数",
}

# 債券利回り。ファイル名の頭の国名 → data/rates.csv の名前
BOND_NAME = {
    "アメリカ": "米国 10年国債",
}

# 終値だけのファイル。data/nikkei_ohlc.csv へ入れる
#   データ日付\t終値
#   2023/1/4\t4849.89
TO_NIKKEI_CLOSE = {
    "日経半導体株指数": "日経半導体株指数",
}

# 日経平均は Yahoo と同じ置き場所・同じ銘柄として入れる
TO_MARKET = {
    "日経平均": {
        "category": "日本指数",
        "name": "日経平均",
        "symbol": "^N225",
        "currency": "JPY",
        "exchange": "Osaka",
    },
}

JPX_HEADER = ["trade_date", "name", "open", "high", "low", "close", "change", "change_pct", "fetched_at"]
RATES_HEADER = ["trade_date", "group", "name", "value", "unit", "change", "updated", "fetched_at"]
NIKKEI_HEADER = ["trade_date", "name", "open", "high", "low", "close", "fetched_at"]


def read_bars(path):
    """四本値を読む。終値の無い行は捨てる。"""
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d = (r.get("Date") or "").strip()
            c = (r.get("Close") or "").strip()
            if not d or not c:
                continue
            out.append(
                {
                    "trade_date": d,
                    "open": (r.get("Open") or "").strip(),
                    "high": (r.get("High") or "").strip(),
                    "low": (r.get("Low") or "").strip(),
                    "close": c,
                }
            )
    return out


def _date(text):
    """2026/8/14 と 2026-08-14 のどちらも受ける。読めなければ None。"""
    text = text.strip()
    for sep in ("/", "-"):
        parts = text.split(sep)
        if len(parts) == 3:
            try:
                y, m, d = (int(x) for x in parts)
            except ValueError:
                return None
            return f"{y:04d}-{m:02d}-{d:02d}"
    return None


def read_jp_bars(path):
    """「日付,終値,始値,高値,安値,…」の形を読む。終値の無い行は捨てる。"""
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d = _date(r.get("日付") or "")
            c = (r.get("終値") or "").strip().replace(",", "")
            if not d or not c:
                continue
            out.append(
                {
                    "trade_date": d,
                    "open": (r.get("始値") or "").strip().replace(",", ""),
                    "high": (r.get("高値") or "").strip().replace(",", ""),
                    "low": (r.get("安値") or "").strip().replace(",", ""),
                    "close": c,
                }
            )
    out.sort(key=lambda x: x["trade_date"])
    return out


def merge_rates(root, rows):
    """data/rates.csv へ。既にある日は触らない。"""
    path = os.path.join(root, "data", "rates.csv")
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[(r["trade_date"], r["group"], r["name"])] = r
    for r in rows:
        key = (r["trade_date"], r["group"], r["name"])
        if key not in existing:
            existing[key] = r

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=RATES_HEADER)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in RATES_HEADER})
    return len(existing)


def read_closes(path):
    """終値だけのファイルを読む。日付は 2023/1/4 の形。"""
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for line in f:
            cells = [c.strip() for c in line.rstrip("\n").split("\t")]
            if len(cells) < 2:
                continue
            d, c = cells[0], cells[1]
            parts = d.split("/")
            if len(parts) != 3 or not c:
                continue          # 見出しの行
            try:
                y, m, day = (int(x) for x in parts)
            except ValueError:
                continue
            out.append({"trade_date": f"{y:04d}-{m:02d}-{day:02d}", "close": c})
    return out


def merge_nikkei(root, rows):
    """data/nikkei_ohlc.csv へ。既にある日は触らない。"""
    path = os.path.join(root, "data", "nikkei_ohlc.csv")
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[(r["trade_date"], r["name"])] = r
    for r in rows:
        key = (r["trade_date"], r["name"])
        if key not in existing:
            existing[key] = r

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=NIKKEI_HEADER)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in NIKKEI_HEADER})
    return len(existing)


def merge_jpx(root, rows):
    """data/jpx_index.csv へ。同じ取引日・指数名は上書きする。"""
    path = os.path.join(root, "data", "jpx_index.csv")
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[(r["trade_date"], r["name"])] = r
    for r in rows:
        key = (r["trade_date"], r["name"])
        # 既にある日は触らない。取得したものを手入力で上書きしない
        if key not in existing:
            existing[key] = r

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=JPX_HEADER)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in JPX_HEADER})
    return len(existing)


def main(argv):
    root = repo_root()
    src = os.path.join(root, "追加")
    stamp = now_jst().isoformat(timespec="seconds")

    if not os.path.isdir(src):
        print("追加/ が無い")
        return 1

    jpx_rows, market_rows = [], []

    for base, name in TO_JPX.items():
        path = os.path.join(src, base + ".csv")
        if not os.path.exists(path):
            print(f"  {base}: ファイルが無い")
            continue
        bars = read_bars(path)
        if not bars:
            print(f"  {name}: 中身が読めない")
            continue
        for b in bars:
            jpx_rows.append({**b, "name": name, "change": "", "change_pct": "", "fetched_at": stamp})
        print(f"  {name:24} {len(bars):6}日  {bars[0]['trade_date']} → {bars[-1]['trade_date']}")

    for base, meta in TO_MARKET.items():
        path = os.path.join(src, base + ".csv")
        if not os.path.exists(path):
            print(f"  {base}: ファイルが無い")
            continue
        bars = read_bars(path)
        if not bars:
            print(f"  {meta['name']}: 中身が読めない")
            continue
        for b in bars:
            market_rows.append(
                {
                    **b,
                    "category": meta["category"],
                    "name": meta["name"],
                    "symbol": meta["symbol"],
                    "source": "manual",
                    "volume": "",
                    "currency": meta["currency"],
                    "exchange": meta["exchange"],
                    "fetched_at": stamp,
                }
            )
        print(f"  {meta['name']:24} {len(bars):6}日  {bars[0]['trade_date']} → {bars[-1]['trade_date']}")

    # 「日付,終値,始値,高値,安値」の形で来る指数
    for base, name in TO_JPX_JP.items():
        path = os.path.join(src, base + ".csv")
        if not os.path.exists(path):
            continue
        bars = read_jp_bars(path)
        if not bars:
            print(f"  {name}: 中身が読めない")
            continue
        for b in bars:
            jpx_rows.append({**b, "name": name, "change": "", "change_pct": "", "fetched_at": stamp})
        print(f"  {name:24} {len(bars):6}日  {bars[0]['trade_date']} → {bars[-1]['trade_date']}")

    # 債券利回り。ファイル名の頭が国名
    rates_rows = []
    for path in sorted(glob.glob(os.path.join(src, "*債券利回りの過去データ*.csv"))):
        country = os.path.basename(path).split(" ")[0]
        name = BOND_NAME.get(country, f"{country} 10年国債")
        bars = read_jp_bars(path)
        if not bars:
            print(f"  {name}: 読めなかった")
            continue
        for b in bars:
            rates_rows.append(
                {
                    "trade_date": b["trade_date"],
                    "group": "国債利回り",
                    "name": name,
                    "value": b["close"],
                    "unit": "%",
                    "change": "",
                    "updated": "",
                    "fetched_at": stamp,
                }
            )
        print(f"  {name:24} {len(bars):6}日  {bars[0]['trade_date']} → {bars[-1]['trade_date']}")

    nikkei_rows = []
    for base, name in TO_NIKKEI_CLOSE.items():
        for ext in (".CSV", ".csv"):
            path = os.path.join(src, base + ext)
            if os.path.exists(path):
                break
        else:
            print(f"  {base}: ファイルが無い")
            continue
        bars = read_closes(path)
        for b in bars:
            nikkei_rows.append(
                {**b, "name": name, "open": "", "high": "", "low": "", "fetched_at": stamp}
            )
        print(f"  {name:24} {len(bars):6}日  {bars[0]['trade_date']} → {bars[-1]['trade_date']}（終値のみ）")

    if nikkei_rows:
        total = merge_nikkei(root, nikkei_rows)
        print(f"\ndata/nikkei_ohlc.csv  {total:,}行")

    if jpx_rows:
        total = merge_jpx(root, jpx_rows)
        print(f"\ndata/jpx_index.csv  {total:,}行")
    if rates_rows:
        total = merge_rates(root, rates_rows)
        print(f"data/rates.csv  {total:,}行")
    if market_rows:
        market_store.merge(root, market_rows)
        print(f"data/overseas_YYYY.csv  {len(market_rows):,}行を投入")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
