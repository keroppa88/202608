"""財務CSVと最新株価から日次の時価総額を作る。

計算方法:
    推定株式数 = NP / EPS
    時価総額   = 推定株式数 * 最新終値

NP/EPS は J-Quants /v2/fins/summary を保存した data/financedata/{code}.csv の
最新開示行（株価日以前）を使う。発行済株式数そのものではなく、EPS 計算上の
加重平均株式数の推定値である。

出力:
    data/market_cap.csv

既存の market_cap.csv は、財務値が欠ける銘柄のフォールバックとしてだけ使う。
"""

import csv
import math
import os
import sys

from common import repo_root

OUT_FIELDS = [
    "code",
    "market_cap_million",
    "as_of",
    "close",
    "finance_date",
    "net_profit",
    "eps",
    "estimated_shares",
    "source",
]


def num(value):
    if value in (None, ""):
        return None
    try:
        n = float(str(value).replace(",", "").strip())
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def load_codes(path):
    codes = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("code") or "").strip().upper()
            if code:
                codes.append(code)
    return sorted(set(codes))


def load_previous(path):
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = (r.get("code") or "").strip().upper()
            cap = num(r.get("market_cap_million"))
            if not code or cap is None or cap <= 0:
                continue
            out[code] = {
                "code": code,
                "market_cap_million": cap,
                "as_of": (r.get("as_of") or "").strip(),
                "close": (r.get("close") or "").strip(),
                "finance_date": (r.get("finance_date") or "").strip(),
                "net_profit": (r.get("net_profit") or "").strip(),
                "eps": (r.get("eps") or "").strip(),
                "estimated_shares": (r.get("estimated_shares") or "").strip(),
                "source": (r.get("source") or "fallback").strip() or "fallback",
            }
    return out


def latest_close(path):
    latest_date = ""
    latest_value = None
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                date = (r.get("Date") or r.get("date") or "").strip()[:10]
                raw = r.get("Close") if r.get("Close") not in (None, "") else r.get("close")
                close = num(raw)
                if not date or close is None or close <= 0:
                    continue
                if date >= latest_date:
                    latest_date = date
                    latest_value = close
    except OSError:
        return None
    if not latest_date or latest_value is None:
        return None
    return latest_date, latest_value


def latest_finance(path, stock_date):
    best = None
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                disc_date = (r.get("DiscDate") or "").strip()[:10]
                if not disc_date or disc_date > stock_date:
                    continue
                np = num(r.get("NP"))
                eps = num(r.get("EPS"))
                if np is None or eps is None or eps == 0:
                    continue
                shares = np / eps
                if not math.isfinite(shares) or shares <= 0:
                    continue
                if best is None or disc_date >= best[0]:
                    best = (disc_date, np, eps, shares)
    except OSError:
        return None
    return best


def clean_number(value, digits=6):
    if value is None:
        return ""
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def main():
    root = repo_root()
    class_path = os.path.join(root, "data", "stock-sectors.csv")
    stocks_dir = os.path.join(root, "data", "stocks")
    finance_dir = os.path.join(root, "data", "financedata")
    out_path = os.path.join(root, "data", "market_cap.csv")

    if not os.path.exists(class_path):
        print(f"分類マスターがない: {class_path}", file=sys.stderr)
        return 2
    if not os.path.isdir(stocks_dir):
        print(f"株価フォルダがない: {stocks_dir}", file=sys.stderr)
        return 2
    if not os.path.isdir(finance_dir):
        print(f"財務フォルダがない: {finance_dir}", file=sys.stderr)
        return 2

    codes = load_codes(class_path)
    previous = load_previous(out_path)
    rows = []
    dynamic = 0
    fallback = 0
    missing = []

    for code in codes:
        price = latest_close(os.path.join(stocks_dir, f"{code}.csv"))
        if price is not None:
            stock_date, close = price
            fin = latest_finance(os.path.join(finance_dir, f"{code}.csv"), stock_date)
            if fin is not None:
                disc_date, np, eps, shares = fin
                cap_million = shares * close / 1_000_000.0
                if math.isfinite(cap_million) and cap_million > 0:
                    rows.append(
                        {
                            "code": code,
                            "market_cap_million": clean_number(cap_million, 3),
                            "as_of": stock_date,
                            "close": clean_number(close, 6),
                            "finance_date": disc_date,
                            "net_profit": clean_number(np, 6),
                            "eps": clean_number(eps, 6),
                            "estimated_shares": clean_number(shares, 3),
                            "source": "NP/EPS*close",
                        }
                    )
                    dynamic += 1
                    continue

        old = previous.get(code)
        if old:
            rows.append(
                {
                    "code": code,
                    "market_cap_million": clean_number(float(old["market_cap_million"]), 3),
                    "as_of": old.get("as_of", ""),
                    "close": old.get("close", ""),
                    "finance_date": old.get("finance_date", ""),
                    "net_profit": old.get("net_profit", ""),
                    "eps": old.get("eps", ""),
                    "estimated_shares": old.get("estimated_shares", ""),
                    "source": "fallback",
                }
            )
            fallback += 1
        else:
            missing.append(code)

    rows.sort(key=lambda r: r["code"])
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print(
        f"時価総額更新: 動的 {dynamic} / フォールバック {fallback} / "
        f"なし {len(missing)} / 対象 {len(codes)}"
    )
    if missing:
        print("  時価総額なしコード: " + " ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
