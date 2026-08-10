"""株価・指数の四本値を取得する（SPEC §4）。

symbols.csv を読み、1銘柄=1リクエストで取得する。
生レスポンスは data/raw/YYYY-MM-DD/ に無加工で保存し、
そこから四本値を抽出して data/YYYY-MM.csv に追記する。

使い方:
    python3 src/fetch_market.py            全銘柄
    python3 src/fetch_market.py TSLA ^GSPC 指定銘柄のみ
"""

import csv
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from common import ExtractError, JST, fetch, now_jst, report, repo_root, save_raw

# 取引所タイムスタンプがこれより古ければ配信停止を疑う。
# 週末・連休を跨ぐため余裕を持たせる（SPEC §9 の RTSI.ME 事例）。
STALE_DAYS = 7

REQUEST_INTERVAL = 0.3

CSV_HEADER = [
    "fetched_at",
    "category",
    "name",
    "symbol",
    "source",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "currency",
    "exchange",
]


def safe_name(symbol):
    """シンボルをファイル名に使える形にする。^GSPC -> _GSPC など。"""
    return re.sub(r"[^A-Za-z0-9._=-]", "_", symbol)


# --------------------------------------------------------------------------
# Yahoo Finance
# --------------------------------------------------------------------------

YAHOO_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{}"
    "?interval=1d&range=5d"
)


def fetch_yahoo(symbol):
    return fetch(YAHOO_URL.format(urllib.parse.quote(symbol, safe="")))


def extract_yahoo(raw):
    """直近の四本値が揃った足を返す。当日足が未確定なことがあるため遡って探す。"""
    doc = json.loads(raw)
    result = (doc.get("chart") or {}).get("result")
    if not result:
        err = (doc.get("chart") or {}).get("error")
        raise ExtractError(f"result が空 ({err})")

    r = result[0]
    meta = r.get("meta") or {}
    stamps = r.get("timestamp")
    if not stamps:
        raise ExtractError("時系列なし（配信停止の疑い）")

    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    for i in range(len(stamps) - 1, -1, -1):
        bar = [q.get(k, [None] * len(stamps))[i] for k in ("open", "high", "low", "close")]
        if all(isinstance(v, (int, float)) for v in bar):
            vol = (q.get("volume") or [None] * len(stamps))[i]
            return {
                # 指数は取引所のローカル日付で扱いたいので JST 変換はしない
                "trade_date": datetime.fromtimestamp(
                    stamps[i], timezone.utc
                ).strftime("%Y-%m-%d"),
                "open": bar[0],
                "high": bar[1],
                "low": bar[2],
                "close": bar[3],
                # 指数の出来高は 0 / None が正常。異常値として弾かない
                "volume": vol,
                "currency": meta.get("currency") or "",
                "exchange": meta.get("exchangeName") or "",
                "long_name": meta.get("longName") or meta.get("shortName") or "",
            }
    raise ExtractError("四本値が全て欠損")


# --------------------------------------------------------------------------
# MOEX ISS（ロシアRTS）
# --------------------------------------------------------------------------

MOEX_URL = (
    "https://iss.moex.com/iss/history/engines/stock/markets/index/securities/{}"
    ".json?from={}&iss.meta=off"
)


def fetch_moex(symbol):
    frm = (now_jst() - timedelta(days=14)).strftime("%Y-%m-%d")
    return fetch(MOEX_URL.format(urllib.parse.quote(symbol, safe=""), frm))


def extract_moex(raw):
    doc = json.loads(raw)
    hist = doc.get("history") or {}
    cols, rows = hist.get("columns") or [], hist.get("data") or []
    if not rows:
        raise ExtractError("history が空")

    idx = {c: i for i, c in enumerate(cols)}
    for row in reversed(rows):
        vals = {k: row[idx[k]] for k in ("OPEN", "HIGH", "LOW", "CLOSE") if k in idx}
        if len(vals) == 4 and all(isinstance(v, (int, float)) for v in vals.values()):
            return {
                "trade_date": row[idx["TRADEDATE"]],
                "open": vals["OPEN"],
                "high": vals["HIGH"],
                "low": vals["LOW"],
                "close": vals["CLOSE"],
                "volume": row[idx["VOLUME"]] if "VOLUME" in idx else None,
                "currency": row[idx["CURRENCYID"]] if "CURRENCYID" in idx else "",
                "exchange": "MOEX",
                "long_name": row[idx["NAME"]] if "NAME" in idx else "",
            }
    raise ExtractError("四本値が揃った行がない")


SOURCES = {
    "yahoo": (fetch_yahoo, extract_yahoo, "json.gz"),
    "moex": (fetch_moex, extract_moex, "json.gz"),
}


# --------------------------------------------------------------------------

def load_symbols(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("symbol")]


def check_freshness(trade_date, today):
    """古すぎる足を弾く。値が返ること自体は正常性の証拠にならない（SPEC §2.4）。"""
    d = datetime.strptime(trade_date, "%Y-%m-%d").date()
    age = (today - d).days
    if age > STALE_DAYS:
        raise ExtractError(f"データが古い（{age}日前 / {trade_date}）")
    if age < 0:
        raise ExtractError(f"未来の日付（{trade_date}）")


def merge_rows(csv_path, new_rows):
    """(symbol, trade_date) をキーに追記する。再実行しても二重にならない。"""
    existing, order = {}, []
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                key = (row["symbol"], row["trade_date"])
                if key not in existing:
                    order.append(key)
                existing[key] = row

    for row in new_rows:
        key = (row["symbol"], row["trade_date"])
        if key not in existing:
            order.append(key)
        existing[key] = row

    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        for key in order:
            w.writerow(existing[key])


def write_latest(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        w.writerows(rows)


def main(argv):
    root = repo_root()
    wanted = set(argv[1:])

    symbols = load_symbols(os.path.join(root, "symbols.csv"))
    if wanted:
        symbols = [s for s in symbols if s["symbol"] in wanted]
        missing = wanted - {s["symbol"] for s in symbols}
        if missing:
            print(f"symbols.csv にない銘柄: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    if not symbols:
        print("対象銘柄がない", file=sys.stderr)
        return 2

    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))
    today = started.date()

    rows, errors = [], []
    for i, sym in enumerate(symbols, 1):
        symbol, source = sym["symbol"], sym.get("source", "yahoo")
        label = f"{sym.get('name') or symbol} ({symbol})"
        try:
            if source not in SOURCES:
                raise ExtractError(f"未知のソース: {source}")
            do_fetch, do_extract, ext = SOURCES[source]

            raw = do_fetch(symbol)
            # 抽出前に必ず保存する。抽出が失敗しても生データは残す
            save_raw(os.path.join(raw_dir, f"{source}_{safe_name(symbol)}.{ext}"), raw)

            bar = do_extract(raw)
            check_freshness(bar["trade_date"], today)

            rows.append(
                {
                    "fetched_at": started.isoformat(timespec="seconds"),
                    "category": sym.get("category", ""),
                    "name": sym.get("name", ""),
                    "symbol": symbol,
                    "source": source,
                    "trade_date": bar["trade_date"],
                    "open": bar["open"],
                    "high": bar["high"],
                    "low": bar["low"],
                    "close": bar["close"],
                    "volume": "" if bar["volume"] is None else bar["volume"],
                    "currency": bar["currency"],
                    "exchange": bar["exchange"],
                }
            )
            print(f"[{i:3}/{len(symbols)}] OK   {label:<34} {bar['trade_date']} {bar['close']}")
        except Exception as e:
            errors.append((label, str(e)))
            print(f"[{i:3}/{len(symbols)}] FAIL {label:<34} {e}")

        time.sleep(REQUEST_INTERVAL)

    if rows:
        merge_rows(os.path.join(root, "data", f"{started.strftime('%Y-%m')}.csv"), rows)
        write_latest(os.path.join(root, "data", "latest.csv"), rows)

    return report([r["symbol"] for r in rows], errors, "相場データ取得")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
