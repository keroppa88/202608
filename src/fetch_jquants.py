"""JPX の J-Quants API から個別株の四本値と出来高を取る。

株価コードを渡したときだけ動く。定期実行はしない。欲しくなったら回す。

    python3 src/fetch_jquants.py 7203 6758
    python3 src/fetch_jquants.py --from 2021-08-20 --to 2026-08-20 7203

返ってきた JSON は無加工で data/raw/YYYY-MM-DD/ に保存し、そこから抜いて
data/overseas_YYYY.csv に書く（SPEC §6）。置き場が他と同じなので、画面には
「日本個別株」としてそのまま出る。

コードは 4桁で渡す。API は普通株を5桁（末尾0）で扱うので、投げるときだけ
5桁にし、保存するときは4桁に戻す。

同じコードで何度回してもよい。(取引日, シンボル) をキーに置き換わるので
二重にならず、後から取り直せば過去の穴も埋まる。

必要なもの:
    JQUANTS_API_KEY   環境変数。GitHub では Secrets に入れる
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

import market_store
from common import ExtractError, FetchError, now_jst, report, repo_root, save_raw

API = "https://api.jquants.com/v2"
REQUEST_INTERVAL = 0.3

# 契約で取れる範囲。既定はここから今日まで
DEFAULT_YEARS = 5

# 調整後があればそちらを採る。分割があると生値は飛ぶため
FIELDS = [
    ("open", "AdjO", "O"),
    ("high", "AdjH", "H"),
    ("low", "AdjL", "L"),
    ("close", "AdjC", "C"),
    ("volume", "AdjVo", "Vo"),
]

# 銘柄名が入っている場所。API の呼び名が変わっても拾えるように並べておく
NAME_KEYS = ("Name", "CompanyName", "CompanyNameJapanese", "NameJapanese")


def api_get(path, params, api_key, raw_dir, label):
    """API を叩いて JSON の生バイト列を返す。

    失敗したら、返ってきた本文も raw に残す。何が起きたかは保存したものを
    見れば分かる、という決まりに合わせる。
    """
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    last = None
    for attempt in range(4):
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return res.read()
        except urllib.error.HTTPError as e:
            body = b""
            try:
                body = e.read()
            except Exception:
                pass
            save_raw(os.path.join(raw_dir, f"jquants_error_{label}_{e.code}.json"), body)
            # 400 番台は投げ直しても同じ。すぐ諦める
            if 400 <= e.code < 500:
                raise FetchError(f"HTTP {e.code} {body[:300].decode('utf-8', 'replace')}")
            last = e
        except Exception as e:
            last = e
        if attempt < 3:
            time.sleep(2**attempt)
    raise FetchError(f"{url} -> {last}")


def fetch_pages(path, params, api_key, raw_dir, label):
    """pagination_key を回し切って、ページごとの生データと中身を返す。"""
    rows = []
    key = None
    for page in range(1, 200):
        p = dict(params)
        if key:
            p["pagination_key"] = key
        raw = api_get(path, p, api_key, raw_dir, label)
        # 抜く前に必ず保存する。抜くのに失敗しても生データは残す
        save_raw(os.path.join(raw_dir, f"jquants_{label}_{page:03d}.json.gz"), raw)
        try:
            got = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise ExtractError(f"JSON として読めない: {e}")
        rows.extend(got.get("data") or [])
        nxt = got.get("pagination_key")
        if not nxt or nxt == key:
            break
        key = nxt
        time.sleep(REQUEST_INTERVAL)
    return rows


def to_five(code):
    """4桁のコードを API の5桁（末尾0）にする。5桁ならそのまま。"""
    c = str(code).strip().upper()
    return c + "0" if len(c) == 4 else c


def to_four(code):
    """API の5桁（末尾0）を4桁に戻す。それ以外はそのまま。"""
    c = str(code).strip().upper()
    return c[:4] if len(c) == 5 and c.endswith("0") else c


def norm_date(v):
    """YYYYMMDD でも YYYY-MM-DD でも YYYY-MM-DD にそろえる。"""
    d = re.sub(r"[^0-9]", "", str(v))
    if len(d) != 8:
        raise ExtractError(f"日付として読めない: {v}")
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}"


def pick(bar):
    """その日の四本値と出来高。調整後と生値を混ぜない。

    調整後が4つとも揃っている日だけ調整後を使う。1つでも欠けていたら全部
    生値にする。片方だけ調整後にすると、同じ行の中で桁が食い違う。
    """
    adj = all(bar.get(a) is not None for _, a, _ in FIELDS[:4])
    out = {}
    for k, a, r in FIELDS:
        v = bar.get(a) if adj else None
        if v is None:
            v = bar.get(r)
        out[k] = v
    return out


def extract(bars, code, name, fetched_at):
    """API の返しから、置き場の形（1行=1銘柄の1日）に直す。"""
    out = []
    for b in bars:
        if not b.get("Date"):
            continue
        vals = pick(b)
        # 四本値が欠けている日は取引が無い日。埋めずに落とす
        if any(vals[k] is None for k in ("open", "high", "low", "close")):
            continue
        out.append(
            {
                "trade_date": norm_date(b["Date"]),
                "category": "日本株",
                "name": name,
                "symbol": code,
                "source": "jquants",
                "open": vals["open"],
                "high": vals["high"],
                "low": vals["low"],
                "close": vals["close"],
                # 出来高が無い日は空欄。0 とは区別する
                "volume": "" if vals["volume"] is None else vals["volume"],
                "currency": "JPY",
                "exchange": "TSE",
                "fetched_at": fetched_at,
            }
        )
    return out


def company_name(api_key, five, raw_dir):
    """銘柄名を引く。取れなければ空で返す（名前が無くても値は入る）。"""
    try:
        rows = fetch_pages("/equities/info", {"code": five}, api_key, raw_dir, f"info_{five}")
    except (FetchError, ExtractError) as e:
        print(f"  銘柄名が引けなかった: {e}")
        return ""
    for r in rows:
        for k in NAME_KEYS:
            if r.get(k):
                return str(r[k])
    print("  銘柄名が返しに無かった。コードだけで入れる")
    return ""


def _option(argv, flag, default=None):
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv):
    api_key = os.environ.get("JQUANTS_API_KEY", "").strip()
    if not api_key:
        print("JQUANTS_API_KEY が無い", file=sys.stderr)
        return 2

    started = now_jst()
    frm = _option(argv, "--from") or (started - timedelta(days=365 * DEFAULT_YEARS)).strftime("%Y-%m-%d")
    to = _option(argv, "--to") or started.strftime("%Y-%m-%d")

    used = {"--from", "--to", frm, to}
    codes = []
    for a in argv[1:]:
        if a in used:
            continue
        for c in re.split(r"[,\s]+", a):
            c = c.strip()
            if not c:
                continue
            if not re.fullmatch(r"[0-9A-Z]{4,5}", c.upper()):
                print(f"株価コードとして読めない: {c}", file=sys.stderr)
                return 2
            if c.upper() not in codes:
                codes.append(c.upper())
    if not codes:
        print("株価コードが要る（例: 7203 6758）", file=sys.stderr)
        return 2

    root = repo_root()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))
    fetched_at = started.isoformat(timespec="seconds")

    print(f"{frm} 〜 {to} を {len(codes)}銘柄ぶん取る")

    rows, ok, errors = [], [], []
    for code in codes:
        five, four = to_five(code), to_four(code)
        label = f"bars_{five}"
        try:
            name = company_name(api_key, five, raw_dir)
            bars = fetch_pages(
                "/equities/bars/daily",
                {"code": five, "from": frm, "to": to},
                api_key,
                raw_dir,
                label,
            )
            got = extract(bars, four, name, fetched_at)
            if not got:
                raise ExtractError(f"四本値が1日も取れなかった（返し {len(bars)}件）")
            rows.extend(got)
            ok.append(four)
            span = [r["trade_date"] for r in got]
            print(f"{four} {name or '(名前なし)'}: {len(got)}日 "
                  f"({min(span)} 〜 {max(span)})")
        except (FetchError, ExtractError) as e:
            errors.append((four, str(e)))
            print(f"{four}: {e}", file=sys.stderr)
        time.sleep(REQUEST_INTERVAL)

    if rows:
        written = market_store.merge(root, rows)
        for year in sorted(written):
            print(f"  data/overseas_{year}.csv: {written[year]}行")

    return report(ok, errors, "J-Quants 個別株")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
