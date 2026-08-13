"""`追加/` に置いた四本値のCSVを、既存の蓄積に取り込む。

手で用意した過去分を入れるための道具。日々の取得とは関係しない。

    追加/日経平均株価.csv     → data/overseas_YYYY.csv（^N225）
    追加/topix.csv 他        → data/jpx_index.csv（JPXの指数名で入れる）

入力の形はどれも同じ。

    Date,Open,High,Low,Close,Volume,TradingValue,UpLimit,LowLimit
    2026-08-10,4078.80,4111.35,4063.49,4100.61,,,,

同じ日・同じ銘柄の行は上書きする。何度流しても二重にならない。

使い方:
    python3 src/import_added.py
"""

import csv
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

# 終値だけのファイル。data/nikkei_ohlc.csv へ入れる
#   データ日付\t終値
#   2023/1/4\t4849.89
TO_NIKKEI_CLOSE = {
    "日経半導体株指数": "日経半導体株指数",
}

# 日経平均は Yahoo と同じ置き場所・同じ銘柄として入れる
TO_MARKET = {
    "日経平均株価": {
        "category": "日本指数",
        "name": "日経平均株価",
        "symbol": "^N225",
        "currency": "JPY",
        "exchange": "Osaka",
    },
}

JPX_HEADER = ["trade_date", "name", "open", "high", "low", "close", "change", "change_pct", "fetched_at"]
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
        for b in bars:
            jpx_rows.append({**b, "name": name, "change": "", "change_pct": "", "fetched_at": stamp})
        print(f"  {name:24} {len(bars):6}日  {bars[0]['trade_date']} → {bars[-1]['trade_date']}")

    for base, meta in TO_MARKET.items():
        path = os.path.join(src, base + ".csv")
        if not os.path.exists(path):
            print(f"  {base}: ファイルが無い")
            continue
        bars = read_bars(path)
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
    if market_rows:
        market_store.merge(root, market_rows)
        print(f"data/overseas_YYYY.csv  {len(market_rows):,}行を投入")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
