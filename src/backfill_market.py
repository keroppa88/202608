"""過去の相場データをまとめて取り込む（SPEC §4K）。

1999-01-01 以降を全銘柄ぶん取り、年ごとのファイルへ書く。
毎日の取得（fetch_market.py）とは別に、必要なときだけ手で走らせる。

毎日の取得と方針が違う点。

    鮮度チェック   しない。古い足を取りに行くのが目的
    四本値の欠け   終値さえあれば入れる。始値・高値・安値は空欄にする
    四本値の不整合 足ごと捨てず、終値だけ残して始値・高値・安値を空欄にする
    抜けている日   飛ばして次へ進む。エラーにしない

「無いものは無い」で構わない。上場が新しい銘柄や、そもそも履歴を配信しない
銘柄（米国REIT・工業用金属指数）は取れる分だけになる。

使い方:
    python3 src/backfill_market.py                  全銘柄・1999年以降
    python3 src/backfill_market.py --from 2010-01-01
    python3 src/backfill_market.py --category 日本株
    python3 src/backfill_market.py TSLA ^GSPC
"""

import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone

import market_store
from common import ExtractError, fetch, now_jst, repo_root, save_raw
from fetch_market import (
    SOURCES,
    _local_date,
    inconsistency,
    load_symbols,
    safe_name,
)

START = "1999-01-01"

YAHOO_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{}"
    "?interval=1d&period1={}&period2={}"
)

MOEX_URL = (
    "https://iss.moex.com/iss/history/engines/stock/markets/index/securities/{}"
    ".json?from={}&start={}&iss.meta=off"
)

REQUEST_INTERVAL = 0.3

# これを超えて崩れている足は、始値・高値・安値を捨てて終値だけ残す
OHLC_TOLERANCE = 0.001


def _num(v):
    return v if isinstance(v, (int, float)) else None


def fetch_yahoo_history(symbol, start_ts):
    url = YAHOO_URL.format(
        urllib.parse.quote(symbol, safe=""), start_ts, 9999999999
    )
    return fetch(url)


def extract_yahoo_history(raw):
    """終値のある足をすべて返す（古い順）。四本値が欠けていても採る。"""
    doc = json.loads(raw)
    result = (doc.get("chart") or {}).get("result")
    if not result:
        raise ExtractError(f"result が空 ({(doc.get('chart') or {}).get('error')})")

    r = result[0]
    meta = r.get("meta") or {}
    stamps = r.get("timestamp") or []
    if not stamps:
        raise ExtractError("時系列なし")

    offset = meta.get("gmtoffset") or 0
    q = (r.get("indicators") or {}).get("quote", [{}])[0]
    today = datetime.now(timezone.utc).date()

    bars = []
    for i, stamp in enumerate(stamps):
        close = _num((q.get("close") or [None] * len(stamps))[i])
        if close is None:
            continue  # 終値が無い日は飛ばす。抜けは許容する
        d = _local_date(stamp, offset)
        if d >= today:
            continue  # 進行中の当日は入れない。確定した足だけを貯める

        o = _num((q.get("open") or [None] * len(stamps))[i])
        h = _num((q.get("high") or [None] * len(stamps))[i])
        l = _num((q.get("low") or [None] * len(stamps))[i])

        if None not in (o, h, l):
            # 崩れている足は終値だけ残す。値は書き換えない（SPEC §2.1）
            if inconsistency({"open": o, "high": h, "low": l, "close": close}) > OHLC_TOLERANCE:
                o = h = l = None

        bars.append(
            {
                "trade_date": d.strftime("%Y-%m-%d"),
                "open": o,
                "high": h,
                "low": l,
                "close": close,
                "volume": _num((q.get("volume") or [None] * len(stamps))[i]),
                "currency": meta.get("currency") or "",
                "exchange": meta.get("exchangeName") or "",
            }
        )
    if not bars:
        raise ExtractError("終値のある足が1本もない")
    return bars


def fetch_moex_history(symbol, start_date):
    """100件ずつ返るので、返らなくなるまでページを送る。"""
    out, cursor = [], 0
    while True:
        raw = fetch(
            MOEX_URL.format(urllib.parse.quote(symbol, safe=""), start_date, cursor)
        )
        doc = json.loads(raw)
        hist = doc.get("history") or {}
        cols, rows = hist.get("columns") or [], hist.get("data") or []
        if not rows:
            break
        idx = {c: i for i, c in enumerate(cols)}
        for row in rows:
            close = _num(row[idx["CLOSE"]]) if "CLOSE" in idx else None
            if close is None:
                continue
            o, h, l = (
                _num(row[idx[k]]) if k in idx else None for k in ("OPEN", "HIGH", "LOW")
            )
            if None not in (o, h, l):
                if inconsistency({"open": o, "high": h, "low": l, "close": close}) > OHLC_TOLERANCE:
                    o = h = l = None
            out.append(
                {
                    "trade_date": row[idx["TRADEDATE"]],
                    "open": o,
                    "high": h,
                    "low": l,
                    "close": close,
                    "volume": _num(row[idx["VOLUME"]]) if "VOLUME" in idx else None,
                    "currency": row[idx["CURRENCYID"]] if "CURRENCYID" in idx else "",
                    "exchange": "MOEX",
                }
            )
        cursor += len(rows)
        time.sleep(REQUEST_INTERVAL)
    if not out:
        raise ExtractError("history が空")
    return out


def _option(argv, name):
    out = []
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            out.append(argv[i + 1])
    return out


def main(argv):
    root = repo_root()
    started = now_jst()
    stamp = started.isoformat(timespec="seconds")

    start_date = (_option(argv, "--from") or [START])[0]
    start_ts = int(datetime.strptime(start_date, "%Y-%m-%d").timestamp())

    only = _option(argv, "--category")
    consumed = {"--from", "--category", start_date, *only}
    wanted = {a for a in argv[1:] if a not in consumed}

    symbols = load_symbols(os.path.join(root, "symbols.csv"))
    if only:
        symbols = [s for s in symbols if s.get("category") in only]
    if wanted:
        symbols = [s for s in symbols if s["symbol"] in wanted]
    if not symbols:
        print("対象銘柄がない")
        return 1

    raw_dir = os.path.join(root, "data", "raw", "backfill")
    print(f"{start_date} 以降 / {len(symbols)}銘柄\n")

    all_rows, failures, total = [], [], 0
    for i, s in enumerate(symbols, 1):
        symbol, source = s["symbol"], s.get("source", "yahoo")
        try:
            if source == "moex":
                bars = fetch_moex_history(symbol, start_date)
            else:
                raw = fetch_yahoo_history(symbol, start_ts)
                save_raw(
                    os.path.join(raw_dir, f"{source}_{safe_name(symbol)}.json.gz"), raw
                )
                bars = extract_yahoo_history(raw)
        except Exception as e:
            failures.append((symbol, str(e).splitlines()[0]))
            print(f"[{i:3}/{len(symbols)}] NG   {s['name']} ({symbol}) {str(e).splitlines()[0][:50]}")
            continue

        partial = sum(1 for b in bars if b["open"] is None)
        for b in bars:
            all_rows.append(
                {
                    "trade_date": b["trade_date"],
                    "category": s.get("category", ""),
                    "name": s.get("name", ""),
                    "symbol": symbol,
                    "source": source,
                    "open": "" if b["open"] is None else b["open"],
                    "high": "" if b["high"] is None else b["high"],
                    "low": "" if b["low"] is None else b["low"],
                    "close": b["close"],
                    "volume": "" if b["volume"] is None else b["volume"],
                    "currency": b["currency"],
                    "exchange": b["exchange"],
                    "fetched_at": stamp,
                }
            )
        total += len(bars)
        note = f"  うち終値のみ {partial}本" if partial else ""
        print(
            f"[{i:3}/{len(symbols)}] OK   {s['name']} ({symbol}) "
            f"{len(bars)}本 {bars[0]['trade_date']}〜{bars[-1]['trade_date']}{note}"
        )
        time.sleep(REQUEST_INTERVAL)

    if not all_rows:
        print("\n1件も取れなかった")
        return 1

    written = market_store.merge(root, all_rows)
    print(f"\n取り込み {total:,}行 / {len(symbols) - len(failures)}銘柄")
    for year, n in sorted(written.items()):
        print(f"  data/overseas_{year}.csv  {n:,}行")
    if failures:
        print(f"\n取れなかった銘柄 {len(failures)}件（無いものは無いままでよい）")
        for symbol, msg in failures:
            print(f"  {symbol}: {msg[:70]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
