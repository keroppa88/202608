"""比率と指標をまとめる。取得はしない。保存済みのものから出すだけ。

    ドル建て日経平均株価     日経平均 / ドル円（どちらも終値）

    NT倍率                   日経平均 / TOPIX（どちらも終値）
                             日経平均は data/overseas_YYYY.csv の ^N225、
                             TOPIX は data/jpx_index.csv。どちらも1本の
                             出どころで通す

    東証先導株比率1-N        売買代金1位〜N位の合計 / 東証プライム売買代金
                             上位 5 / 10 / 20 / 30 の4本

    日経/プライム・売買代金比率
                             日経平均の構成銘柄の売買代金合計 /
                             東証プライム売買代金
                             こちらは割り算をしない。日経のページに
                             「対市場占有率」として出ている値をそのまま使う。
                             売買代金合計はページに兆円・小数2桁でしか
                             出ておらず、割って出すと 0.1ポイントほど狂う

    日経予想PER/プライム予想PER
    日経平均PBR/プライムPBR
                             日経平均とプライム全銘柄の比。割高・割安の差

    プライム予想PER / 日経予想PER / プライムPBR / 日経平均PBR
                             ページに出ている値をそのまま入れる。計算しない
                             PBR はページに予想と前期基準の別が無く、
                             純資産倍率が1つだけ出ている。それを使う

    イールドスプレッド       プライム株式益回り − 長期金利
                             プライム株式益回り = 1 / プライム予想PER
                             長期金利 = 日本国債10年利回り

読むもの

    data/overseas_YYYY.csv       日経平均（^N225）とドル円（USDJPY=X）の終値
    data/jpx_index.csv           TOPIX の終値
    data/rank_trading_value.csv  東証の売買代金ランキング（円）
    data/nikkei_kabu.csv         東証プライムの売買代金（百万円）
                                 PER・PBR（株価収益率 / 純資産倍率）
    data/nikkei225_detail.csv    日経平均構成銘柄の売買代金の対市場占有率（％）
    data/rates.csv               日本国債10年利回り（％）

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
import glob
import os
import sys

from common import now_jst, report, repo_root

TOPS = (5, 10, 20, 30)
LEAD_NAME = "東証先導株比率1-{}"
N225_NAME = "日経/プライム・売買代金比率"
NT_NAME = "NT倍率"
USD_NAME = "ドル建て日経平均株価"
SPREAD_NAME = "日本株イールドスプレッド"
JGB10 = "日本 10年国債"

# ページに出ている値をそのまま入れるもの
#   名前: (節, 項目, 欄)
PLAIN = {
    "プライム予想PER": ("株価収益率（連結決算ベース）", "プライム全銘柄", "予想"),
    "日経予想PER": ("株価収益率（連結決算ベース）", "日経平均", "予想"),
    "プライムPBR": ("純資産倍率（連結決算ベース）", "プライム全銘柄", "純資産倍率"),
    "日経平均PBR": ("純資産倍率（連結決算ベース）", "日経平均", "純資産倍率"),
}

# 割り算して出すもの
#   名前: (分子の名前, 分母の名前)
PAIRS = {
    "日経予想PER/プライム予想PER": ("日経予想PER", "プライム予想PER"),
    "日経平均PBR/プライムPBR": ("日経平均PBR", "プライムPBR"),
}

# 画面に並べる順。小さいほど先
ORDER = {
    USD_NAME: 0, NT_NAME: 1,
    "日経予想PER/プライム予想PER": 101, "日経平均PBR/プライムPBR": 102,
    "プライム予想PER": 103, "日経予想PER": 104,
    "プライムPBR": 105, "日経平均PBR": 106,
    SPREAD_NAME: 107,
}

HEADER = ["trade_date", "name", "close", "numerator", "denominator", "calculated_at"]


def read_overseas_close(data_dir, symbol):
    """{取引日: 終値} を返す。年ごとに分かれているので全部読む。"""
    out = {}
    for path in sorted(glob.glob(os.path.join(data_dir, "overseas_*.csv"))):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                if r["symbol"] != symbol or not r["close"]:
                    continue
                try:
                    out[r["trade_date"]] = float(r["close"])
                except ValueError:
                    continue
    return out


def read_jpx_close(path, name):
    """{取引日: 終値} を返す。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["name"] != name or not r["close"]:
                continue
            try:
                out[r["trade_date"]] = float(r["close"])
            except ValueError:
                continue
    return out


def read_kabu_value(path, section, item, column):
    """{取引日: 値} を返す。国内株式指標のページの1項目ぶん。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["section"] != section or r["item"] != item or r["column"] != column:
                continue
            try:
                out[r["trade_date"]] = float(r["value"])
            except (TypeError, ValueError):
                continue
    return out


def read_rate(path, name):
    """{取引日: 利回り（％）} を返す。"""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["name"] != name:
                continue
            try:
                out[r["trade_date"]] = float(r["value"])
            except (TypeError, ValueError):
                continue
    return out


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


def read_n225_share(path):
    """{取引日: 日経平均構成銘柄の売買代金の対市場占有率（％）} を返す。

    売買代金合計から自分で割って出すこともできるが、その値はページに
    兆円・小数2桁でしか出ていないため 0.1ポイントほど狂う。
    同じ数字がページに出ているので、そのまま使う。
    """
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if r["key"] != "売買代金合計" or r["sub"] != "対市場占有率":
                continue
            try:
                out[r["trade_date"]] = float(r["value"])
            except (TypeError, ValueError):
                continue
    return out


def calc(nikkei, topix, usdjpy, plain, jgb, ranking, prime, share):
    """出せる日ぶんだけ行を作る。順位に抜けがある日は、その本数を出さない。"""
    rows, skipped = [], []

    def put(d, name, close, num="", den=""):
        rows.append({"trade_date": d, "sort": ORDER.get(name, 50), "name": name,
                     "close": close, "numerator": num, "denominator": den})

    # ドル建て日経平均株価。日経平均は1985年から、ドル円は1999年から
    for d in sorted(set(nikkei) & set(usdjpy)):
        if usdjpy[d]:
            put(d, USD_NAME, round(nikkei[d] / usdjpy[d], 2), nikkei[d], usdjpy[d])

    # NT倍率。日経平均は1985年から、TOPIXは2004年からあるので両方そろう日だけ
    for d in sorted(set(nikkei) & set(topix)):
        if topix[d]:
            put(d, NT_NAME, round(nikkei[d] / topix[d], 2), nikkei[d], topix[d])

    # PER・PBR。ページの値をそのまま入れる
    for name, series in plain.items():
        for d, v in sorted(series.items()):
            put(d, name, v)

    # 日経とプライムの比
    for name, (a, b) in PAIRS.items():
        for d in sorted(set(plain[a]) & set(plain[b])):
            if plain[b][d]:
                put(d, name, round(plain[a][d] / plain[b][d], 3), plain[a][d], plain[b][d])

    # イールドスプレッド。プライム株式益回り − 長期金利
    per = plain["プライム予想PER"]
    for d in sorted(set(per) & set(jgb)):
        if per[d]:
            earn = 100 / per[d]
            put(d, SPREAD_NAME, round(earn - jgb[d], 2), round(earn, 3), jgb[d])

    days = sorted(set(ranking) | set(share))

    for d in days:
        # 日経/プライムはページに出ている値をそのまま使う。割り算をしないので
        # プライム売買代金が無い日でも出せる
        s = share.get(d)
        if s is not None:
            put(d, N225_NAME, s)
        else:
            skipped.append((d, "日経平均の対市場占有率が無い"))

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
            put(d, LEAD_NAME.format(n), round(top / p * 100, 2), top, p)

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

    kabu = os.path.join(data, "nikkei_kabu.csv")
    nikkei = read_overseas_close(data, "^N225")
    usdjpy = read_overseas_close(data, "USDJPY=X")
    topix = read_jpx_close(os.path.join(data, "jpx_index.csv"), "TOPIX")
    plain = {name: read_kabu_value(kabu, *where) for name, where in PLAIN.items()}
    jgb = read_rate(os.path.join(data, "rates.csv"), JGB10)
    ranking = read_ranking(os.path.join(data, "rank_trading_value.csv"))
    prime = read_prime(kabu)
    share = read_n225_share(os.path.join(data, "nikkei225_detail.csv"))
    print(f"日経平均 {len(nikkei)}日 / ドル円 {len(usdjpy)}日 / TOPIX {len(topix)}日 / "
          f"PER・PBR {min(len(v) for v in plain.values())}日 / "
          f"日本国債10年 {len(jgb)}日 / "
          f"ランキング {len(ranking)}日 / プライム売買代金 {len(prime)}日 / "
          f"日経平均の対市場占有率 {len(share)}日")

    rows, skipped = calc(nikkei, topix, usdjpy, plain, jgb, ranking, prime, share)
    if not rows:
        return report([], [("計算", "出せる日が1日も無い")], "比率")

    for name in (USD_NAME, NT_NAME):
        got = sorted((r for r in rows if r["name"] == name), key=lambda r: r["trade_date"])
        if got:
            print(f"  {name:12} {got[0]['trade_date']} 〜 {got[-1]['trade_date']}  "
                  f"{len(got):5}日  最新 {got[-1]['close']}")

    daily = {USD_NAME, NT_NAME}
    for d in sorted({r["trade_date"] for r in rows if r["name"] not in daily}):
        got = {r["name"]: r["close"] for r in rows if r["trade_date"] == d}
        line = "  ".join(f"1-{n} {got[LEAD_NAME.format(n)]:5.2f}%"
                         for n in TOPS if LEAD_NAME.format(n) in got)
        if N225_NAME in got:
            line += f"   日経/プライム {got[N225_NAME]:5.2f}%"
        line += (f"   PER 日経 {got.get('日経予想PER', 0):.2f} / プライム "
                 f"{got.get('プライム予想PER', 0):.2f}"
                 f"   PBR 日経 {got.get('日経平均PBR', 0):.2f} / プライム "
                 f"{got.get('プライムPBR', 0):.2f}")
        if SPREAD_NAME in got:
            line += f"   スプレッド {got[SPREAD_NAME]:.2f}"
        print(f"  {d}  {line}")
    for d, why in skipped:
        print(f"  {d}  出せない: {why}")

    write(os.path.join(data, "ratios.csv"), rows, now_jst().isoformat(timespec="seconds"))
    print(f"\ndata/ratios.csv  {len(rows)}行")
    return report([r["name"] for r in rows], [], "比率")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
