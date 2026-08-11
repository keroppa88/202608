"""日経のランキングページの表示テキストから順位表を取り出す（SPEC §4F）。

https://www.nikkei.com/marketdata/ranking-jp/trading-value/  売買代金
https://www.nikkei.com/marketdata/ranking-jp/access/          株価検索数

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

どちらのページも同じ形をしている。

    2026年08月10日 15:50更新       ← 日付
    順位 / 銘柄名 / …列名…         ← 見出し。20件ごとに繰り返される
    1                              ← 順位
    キオクシア                      ← 銘柄名
    285A                           ← コード
    プライム                        ← 市場
    1,570,008,575,000              ← 列の値が続く
    48,010
    (15:30)                        ← 時刻。値ではない
    +280
    +0.59%

銘柄名は「名前 コード 市場」の順で並ぶ。コードは4桁の数字か、
`285A` のような数字と英字の混じった新しい形式。

この3つは**行が分かれている場合と、1行に収まっている場合の両方**がある。
見え方は取り方で変わるので、どちらでも読めるようにしてある。
"""

import re
from datetime import date

# 「2026年08月10日 15:50 更新」
UPDATED = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})\s*更新")

# 「キオクシア 285A プライム」が1行に収まっている場合
STOCK = re.compile(r"^(.+?)\s+(\d{4}|\d{3}[A-Z]|[0-9A-Z]{4})\s+(プライム|スタンダード|グロース|.+)$")

# 行が分かれている場合。コードと市場でそれと分かる
CODE = re.compile(r"^(\d{4}|\d{3}[A-Z]|[0-9A-Z]{4})$")
MARKETS = ("プライム", "スタンダード", "グロース")

RANK = re.compile(r"^\d{1,3}$")

# 「(15:30)」は値ではなく約定時刻
TIME = re.compile(r"^\(\d{1,2}:\d{2}\)$")

# 前日比が動かなかった銘柄は「±0」「±0.00 %」と出る
NUMBER = re.compile(r"^[+\-±]?[\d,]+\.?\d*\s*%?$")


class ExtractError(Exception):
    pass


def _num(text):
    text = text.strip().replace(",", "").replace("%", "").replace("±", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def find_date(text):
    """「◯年◯月◯日 ◯:◯ 更新」から日付を返す。"""
    m = UPDATED.search(text)
    if not m:
        raise ExtractError("「◯年◯月◯日 ◯◯:◯◯ 更新」が見つからない")
    y, mo, d = (int(g) for g in m.groups()[:3])
    return date(y, mo, d)


def parse(text, columns, limit=None):
    """順位表を返す。

    columns … 銘柄名の後ろに並ぶ値の名前。例 ["売買代金", "現在値", "前日比", "前日比率"]
    limit   … 上位何位までか。None なら全件

    戻り値: [{rank, code, name, market, <columns...>}]
    """
    trade_date = find_date(text)
    # ブラウザで取ると表のセルがタブ区切りの1行になる。1セル1行に開く
    lines = [c.strip() for ln in text.split("\n") for c in ln.split("\t") if c.strip()]

    rows = []
    i = 0
    while i < len(lines):
        # 「順位」に見える行の次が銘柄名なら、そこから1件ぶん読む
        if not RANK.match(lines[i]) or i + 1 >= len(lines):
            i += 1
            continue
        # 銘柄は1行にまとまっている場合と、名前・コード・市場が別行の場合がある
        stock = STOCK.match(lines[i + 1])
        if stock:
            name, code, market = (g.strip() for g in stock.groups())
            after = i + 2
        elif (
            i + 3 < len(lines)
            and CODE.match(lines[i + 2])
            and lines[i + 3] in MARKETS
        ):
            name, code, market = lines[i + 1], lines[i + 2], lines[i + 3]
            after = i + 4
        else:
            i += 1
            continue

        rank = int(lines[i])
        if rows and rank != rows[-1]["rank"] + 1:
            i += 1
            continue  # 順位が飛んでいれば表の外

        row = {
            "trade_date": trade_date,
            "rank": rank,
            "code": code,
            "name": name,
            "market": market,
        }

        # 銘柄名の次から、時刻の行を飛ばしつつ列の数だけ値を読む
        values, j = [], after
        while j < len(lines) and len(values) < len(columns):
            if TIME.match(lines[j]):
                j += 1
                continue
            if not NUMBER.match(lines[j]):
                break
            values.append(_num(lines[j]))
            j += 1

        if len(values) < len(columns):
            i += 1
            continue  # 値が足りない行は表の外とみなす

        row.update(dict(zip(columns, values)))
        rows.append(row)
        i = j

        if limit and len(rows) >= limit:
            break

    if not rows:
        raise ExtractError("順位の行が1件も取れない")
    return rows
