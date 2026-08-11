"""株価・指数の四本値を取得する（SPEC §4）。

symbols.csv を読み、1銘柄=1リクエストで取得する。
生レスポンスは data/raw/YYYY-MM-DD/ に無加工で保存し、
そこから四本値を抽出して data/overseas_YYYY.csv に追記する（SPEC §6）。

取得する範囲は分類で絞れる。市場の開いている時間が違うため、
日本株は夕方、それ以外は朝の枠で動かしている（SPEC §8）。

使い方:
    python3 src/fetch_market.py                     全銘柄
    python3 src/fetch_market.py TSLA ^GSPC          指定銘柄のみ
    python3 src/fetch_market.py --category 日本株    その分類だけ
    python3 src/fetch_market.py --exclude 日本株     その分類を除く
"""

import csv
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

import market_store
from common import ExtractError, JST, fetch, now_jst, report, repo_root, save_raw

# 取引所タイムスタンプがこれより古ければ配信停止を疑う。
# 週末・連休を跨ぐため余裕を持たせる（SPEC §9 の RTSI.ME 事例）。
STALE_DAYS = 7

# 四本値の整合性（安値 <= 始値/終値 <= 高値）が崩れたときに許す幅。
# 配信側の集計のずれで 0.05% 程度は日常的に起きるため、それは通す。
# これを超えるものは配信側の異常を疑い、エラーとして記録する。
OHLC_TOLERANCE = 0.001  # 0.1%

REQUEST_INTERVAL = 0.3

# 列と置き場所は market_store が持つ（年ごとにファイルを分ける）
HEADER = market_store.HEADER


def safe_name(symbol):
    """シンボルをファイル名に使える形にする。^GSPC -> _GSPC など。"""
    return re.sub(r"[^A-Za-z0-9._=-]", "_", symbol)


# --------------------------------------------------------------------------
# Yahoo Finance
# --------------------------------------------------------------------------

# range=1mo を使う。5d だと S&P500 セクター指数などは足が1本しか返らず、
# その1本が進行中セッションだと確定足が1本も得られない（実測）。
YAHOO_URL = (
    "https://query1.finance.yahoo.com/v8/finance/chart/{}"
    "?interval=1d&range=1mo"
)


def fetch_yahoo(symbol):
    return fetch(YAHOO_URL.format(urllib.parse.quote(symbol, safe="")))


def _local_date(stamp, gmtoffset):
    """取引所ローカルの日付。日付の比較は必ず取引所時間で行う。"""
    return datetime.fromtimestamp(stamp + gmtoffset, timezone.utc).date()


def _in_progress(meta, stamp, now_ts):
    """stamp の足が「まだ終わっていないセッション」のものなら True。

    取引時間中に叩くと、Yahoo は進行中セッションの足も四本値が埋まった状態で返す。
    その close はその瞬間の値であって終値ではないため、確定足にしてはいけない。

    判定は「そのセッションの終了時刻を過ぎたか」で行う。
    バーのタイムスタンプは銘柄によってセッション開始時刻だったり
    最終約定時刻だったりして揃わないため、時刻の一致では判定できない。
    """
    end = ((meta.get("currentTradingPeriod") or {}).get("regular") or {}).get("end")
    if not end or now_ts >= end:
        return False  # そのセッションは終了済み。休場日は次回セッションを指すので日付が一致しない
    offset = meta.get("gmtoffset") or 0
    return _local_date(stamp, offset) == _local_date(end, offset)


def extract_yahoo(raw):
    """確定した四本値を**すべて**返す（新しい順）。

    レスポンスには1か月分の足が入っているので、毎回まとめて取り込む。
    取得を1日飛ばしても次の実行で自動的に埋まり、休場日はそもそも足が無いので
    「更新なし」と「取り逃し」を区別する必要がなくなる。
    """
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

    now_ts = int(datetime.now(timezone.utc).timestamp())
    offset = meta.get("gmtoffset") or 0
    q = (r.get("indicators") or {}).get("quote", [{}])[0]

    bars = []
    for i in range(len(stamps) - 1, -1, -1):
        if _in_progress(meta, stamps[i], now_ts):
            continue
        ohlc = [q.get(k, [None] * len(stamps))[i] for k in ("open", "high", "low", "close")]
        if not all(isinstance(v, (int, float)) for v in ohlc):
            continue
        bars.append(
            {
                # 日付は取引所ローカル。UTC に直すと市場ごとに1日ずれる
                "trade_date": _local_date(stamps[i], offset).strftime("%Y-%m-%d"),
                "open": ohlc[0],
                "high": ohlc[1],
                "low": ohlc[2],
                "close": ohlc[3],
                # 指数の出来高は 0 / None が正常。異常値として弾かない
                "volume": (q.get("volume") or [None] * len(stamps))[i],
                "currency": meta.get("currency") or "",
                "exchange": meta.get("exchangeName") or "",
            }
        )
    if not bars:
        raise ExtractError("確定した四本値が1本もない")
    return bars


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
    """確定した四本値をすべて返す（新しい順）。history は完了済みセッションのみを含む。"""
    doc = json.loads(raw)
    hist = doc.get("history") or {}
    cols, rows = hist.get("columns") or [], hist.get("data") or []
    if not rows:
        raise ExtractError("history が空")

    idx = {c: i for i, c in enumerate(cols)}
    bars = []
    for row in reversed(rows):
        vals = {k: row[idx[k]] for k in ("OPEN", "HIGH", "LOW", "CLOSE") if k in idx}
        if len(vals) != 4 or not all(isinstance(v, (int, float)) for v in vals.values()):
            continue
        bars.append(
            {
                "trade_date": row[idx["TRADEDATE"]],
                "open": vals["OPEN"],
                "high": vals["HIGH"],
                "low": vals["LOW"],
                "close": vals["CLOSE"],
                "volume": row[idx["VOLUME"]] if "VOLUME" in idx else None,
                "currency": row[idx["CURRENCYID"]] if "CURRENCYID" in idx else "",
                "exchange": "MOEX",
            }
        )
    if not bars:
        raise ExtractError("四本値が揃った行がない")
    return bars


SOURCES = {
    "yahoo": (fetch_yahoo, extract_yahoo, "json.gz"),
    "moex": (fetch_moex, extract_moex, "json.gz"),
}


# --------------------------------------------------------------------------

def load_symbols(path):
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("symbol")]


def inconsistency(bar):
    """安値 <= 始値/終値 <= 高値 の崩れ幅を相対値で返す。整合していれば 0。

    高値が終値より安い、といった足は物理的にありえず、
    値幅やローソク足の計算を壊す。値は書き換えない。
    配信元にない数字を作らないため（SPEC §2.1）。
    """
    o, h, l, c = (bar[k] for k in ("open", "high", "low", "close"))
    gap = max(l - min(o, c), max(o, c) - h, 0)
    return gap / l if gap and l else 0.0


def drop_inconsistent(bars, label):
    """不整合な足を除いて返す。最新の足が壊れていた場合だけ例外にする。

    過去の足は毎回取り込み直すので、そこで例外にすると同じ異常を何日も
    通知し続けることになる（§2.4 の通知が形骸化する）。除いて記録に留める。
    最新の足はその日に届いたばかりの異常なので、気づけるようエラーにする。
    """
    good = []
    for i, bar in enumerate(bars):
        rate = inconsistency(bar)
        if rate <= OHLC_TOLERANCE:
            good.append(bar)
            continue
        detail = (
            f"{bar['trade_date']} 乖離 {rate * 100:.3f}% "
            f"(O={bar['open']} H={bar['high']} L={bar['low']} C={bar['close']})"
        )
        if i == 0:
            raise ExtractError(f"最新の足が不整合 {detail}")
        print(f"     ※ {label}: 不整合な足を除外 {detail}")
    if not good:
        raise ExtractError("整合する足が1本もない")
    return good


def check_freshness(trade_date, today):
    """古すぎる足を弾く。値が返ること自体は正常性の証拠にならない（SPEC §2.4）。"""
    d = datetime.strptime(trade_date, "%Y-%m-%d").date()
    age = (today - d).days
    if age > STALE_DAYS:
        raise ExtractError(f"データが古い（{age}日前 / {trade_date}）")
    if age < 0:
        raise ExtractError(f"未来の日付（{trade_date}）")


def _option(argv, name):
    """--name 値 を取り出す。複数回指定できる。"""
    out = []
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            out.append(argv[i + 1])
    return out


def main(argv):
    root = repo_root()
    only = _option(argv, "--category")
    skip = _option(argv, "--exclude")
    consumed = {"--category", "--exclude", *only, *skip}
    wanted = {a for a in argv[1:] if a not in consumed}

    symbols = load_symbols(os.path.join(root, "symbols.csv"))
    if only:
        symbols = [s for s in symbols if s.get("category") in only]
    if skip:
        symbols = [s for s in symbols if s.get("category") not in skip]
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

            bars = do_extract(raw)
            # 鮮度は最新の足で見る。過去分は古くて当然なので対象外
            check_freshness(bars[0]["trade_date"], today)
            bars = drop_inconsistent(bars, label)

            for bar in bars:
                rows.append(
                    {
                        "trade_date": bar["trade_date"],
                        "category": sym.get("category", ""),
                        "name": sym.get("name", ""),
                        "symbol": symbol,
                        "source": source,
                        "open": bar["open"],
                        "high": bar["high"],
                        "low": bar["low"],
                        "close": bar["close"],
                        # 出来高が取れない銘柄は空欄。0 とは区別する
                        "volume": "" if bar["volume"] is None else bar["volume"],
                        "currency": bar["currency"],
                        "exchange": bar["exchange"],
                        "fetched_at": started.isoformat(timespec="seconds"),
                    }
                )
            print(
                f"[{i:3}/{len(symbols)}] OK   {label:<34} "
                f"{bars[0]['trade_date']} {bars[0]['close']}  ({len(bars)}本)"
            )
        except Exception as e:
            errors.append((label, str(e)))
            print(f"[{i:3}/{len(symbols)}] FAIL {label:<34} {e}")

        time.sleep(REQUEST_INTERVAL)

    if rows:
        market_store.merge(root, rows)

    return report(sorted({r["symbol"] for r in rows}), errors, "相場データ取得")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
