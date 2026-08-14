"""売買代金の比率を出す。取得はしない。保存済みのものから計算するだけ。

    東証先導株比率1-N        売買代金1位〜N位の合計 / 東証プライム売買代金
                             上位 5 / 10 / 20 / 30 の4本

    日経/プライム・売買代金比率
                             日経平均の構成銘柄の売買代金合計 /
                             東証プライム売買代金

読むもの

    data/rank_trading_value.csv  東証の売買代金ランキング（円）
    data/nikkei_kabu.csv         東証プライムの売買代金（百万円）
    data/nikkei225_detail.csv    日経平均構成銘柄の売買代金合計（兆円）

書くもの

    data/ratios.csv  trade_date, name, close, numerator, denominator,
                     calculated_at

**どれかが欠けている日は計算しない。** 埋め合わせはしない。
ランキングは当日ぶんしかページに出ないので、取り逃した日は後から取れない。
無いものを別の何かで埋めると、動いているように見えて中身が違うものになる。

毎回すべての日を計算し直す。何度流しても同じ結果になる。

使い方:
    python3 src/calc_ratios.py
"""

import csv
import os
import sys

from common import now_jst, report, repo_root

TOPS = (5, 10, 20, 30)
LEAD_NAME = "東証先導株比率1-{}"
N225_NAME = "日経/プライム・売買代金比率"

HEADER = ["trade_date", "name", "close", "numerator", "denominator", "calculated_at"]


def read_ranking(path):
    """{取引日: {順位: 売買代金（円）}} を返す。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rank, turnover = int(r["rank"]), float(r["turnover"])
            except (TypeError, ValueError):
                continue
            out.setdefault(r["trade_date"], {})[rank] = turnover
    return out


def read_prime(path):
    """{取引日: 東証プライムの売買代金（円）} を返す。ページの単位は百万円。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["market"] != "東証" or r["item"] != "売買代金" or r["column"] != "プライム":
                continue
            try:
                out[r["trade_date"]] = float(r["value"]) * 1_000_000
            except (TypeError, ValueError):
                continue
    return out


def read_n225_turnover(path):
    """{取引日: 日経平均構成銘柄の売買代金合計（円）} を返す。ページの単位は兆円。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["key"] != "売買代金合計" or (r["sub"] or "").strip():
                continue          # 「対市場占有率」の行は分母が違うので使わない
            try:
                out[r["trade_date"]] = float(r["value"]) * 1_000_000_000_000
            except (TypeError, ValueError):
                continue
    return out


def calc(ranking, prime, n225):
    """出せる日ぶんだけ行を作る。順位に抜けがある日は、その本数を出さない。"""
    rows, skipped = [], []
    days = sorted(set(ranking) | set(n225))

    for d in days:
        p = prime.get(d)
        if not p:
            skipped.append((d, "プライム売買代金が無い"))
            continue

        by_rank = ranking.get(d)
        for i, n in enumerate(TOPS):
            if not by_rank:
                if i == 0:
                    skipped.append((d, "売買代金ランキングが無い"))
                continue
            if any(k not in by_rank for k in range(1, n + 1)):
                skipped.append((d, f"1〜{n}位に抜けがある"))
                continue
            top = sum(by_rank[k] for k in range(1, n + 1))
            rows.append({"trade_date": d, "sort": n, "name": LEAD_NAME.format(n),
                         "close": round(top / p * 100, 2),
                         "numerator": top, "denominator": p})

        t = n225.get(d)
        if t:
            rows.append({"trade_date": d, "sort": 99, "name": N225_NAME,
                         "close": round(t / p * 100, 2),
                         "numerator": t, "denominator": p})
        else:
            skipped.append((d, "日経平均の売買代金合計が無い"))

    return rows, skipped


def write(path, rows, stamp):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["trade_date"], r["sort"])):
            w.writerow({**{k: r[k] for k in HEADER if k != "calculated_at"},
                        "calculated_at": stamp})


def main(argv):
    root = repo_root()
    data = os.path.join(root, "data")

    ranking = read_ranking(os.path.join(data, "rank_trading_value.csv"))
    prime = read_prime(os.path.join(data, "nikkei_kabu.csv"))
    n225 = read_n225_turnover(os.path.join(data, "nikkei225_detail.csv"))
    print(f"ランキング {len(ranking)}日 / プライム売買代金 {len(prime)}日 / "
          f"日経平均の売買代金合計 {len(n225)}日")

    rows, skipped = calc(ranking, prime, n225)
    if not rows:
        return report([], [("計算", "出せる日が1日も無い")], "売買代金比率")

    for d in sorted({r["trade_date"] for r in rows}):
        got = {r["name"]: r["close"] for r in rows if r["trade_date"] == d}
        line = "  ".join(f"1-{n} {got[LEAD_NAME.format(n)]:5.2f}%"
                         for n in TOPS if LEAD_NAME.format(n) in got)
        if N225_NAME in got:
            line += f"   日経/プライム {got[N225_NAME]:5.2f}%"
        print(f"  {d}  {line}")
    for d, why in skipped:
        print(f"  {d}  出せない: {why}")

    write(os.path.join(data, "ratios.csv"), rows, now_jst().isoformat(timespec="seconds"))
    print(f"\ndata/ratios.csv  {len(rows)}行")
    return report([r["name"] for r in rows], [], "売買代金比率")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
