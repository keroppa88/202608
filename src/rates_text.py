"""金利のページの表示テキストから、利回りと政策金利を抜き出す（SPEC §4H）。

入力は「画面に見えている文字」だけ。HTMLは見ない（CLAUDE.md）。

    国債利回り  https://jp.tradingeconomics.com/bonds
                各国の10年債。地域ごとに同じ国が繰り返し出るので重複は除く

    政策金利    https://www.rakuten-sec.co.jp/web/market/data/list.html
                4件のみ（日本 無担保コール翌日物 / 日本 公定歩合 /
                アメリカ フェデラルファンド金利 / ユーロ 市場調整金利）

どちらもタブ区切りの1行として画面に出ている。
"""

import re
from datetime import date

# 2026-08-11 のような日付。当日更新中の行は "03:22" と時刻だけになる
ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
CLOCK = re.compile(r"^\d{1,2}:\d{2}$")

# 2026/08/10 のような日付（楽天）
SLASH_DATE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})")

NUMBER = re.compile(r"^[+-]?[\d,]+\.?\d*$")

# tradingeconomics から取る国。ここに無い国は取らない（画面の表記のまま）
COUNTRIES = (
    "米国",
    "イギリス",
    "日本",
    "オーストラリア",
    "ドイツ",
    "ブラジル",
    "ロシア",
    "インド",
    "カナダ",
    "イタリア",
    "フランス",
    "南アフリカ",
    "中国",
    "スイス",
    "メキシコ",
    "オランダ",
    "ニュージーランド",
    "ポルトガル",
    "韓国",
    "スペイン",
    "ギリシャ",
    "トルコ",
    "台湾",
    "タイ",
    "ベトナム",
    "香港",
    "インドネシア",
    "マレーシア",
    "パキスタン",
    "フィリピン",
    "ケニア",
    "ナイジェリア",
    "イスラエル",
    "シンガポール",
    "ノルウェー",
    "フィンランド",
)

# 楽天から取る政策金利。ここに無いものは取らない
POLICY_RATES = (
    "日本 無担保コール翌日物",
    "日本 公定歩合",
    "アメリカ フェデラルファンド金利",
    "ユーロ 市場調整金利",
)


class ExtractError(Exception):
    pass


def _cells(line):
    """タブ区切りの1行を、前後の空白を落として並べ直す。空の欄は捨てる。"""
    return [c.strip() for c in line.split("\t") if c.strip()]


def _number(text):
    if not NUMBER.match(text):
        return None
    return float(text.replace(",", ""))


def parse_bonds(text, today=None):
    """tradingeconomics の画面から各国の10年債利回りを抜く。

    1行はこうなっている（先頭に空欄が付く）:

        \t米国\t4.6910\t 0.0220\t0.07%\t0.07%\t0.52%\t0.40%\t2026-08-11

    地域の節ごとに同じ国が繰り返し出るので、最初に出たものだけを採る。
    """
    today = today or date.today()
    rows, seen = [], set()

    for line in text.split("\n"):
        c = _cells(line)
        if len(c) != 8:
            continue

        name, value, change = c[0], _number(c[1]), _number(c[2])
        stamp = c[7]

        # 「ヨーロッパ 価格 前日比 …」のような見出し行を外す
        if value is None:
            continue

        m = ISO_DATE.match(stamp)
        if m:
            trade_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        elif CLOCK.match(stamp):
            # 当日ザラ場の更新。日付が出ていないので取得日を使う
            trade_date = today
        else:
            continue

        if name not in COUNTRIES or name in seen:
            continue
        seen.add(name)

        rows.append(
            {
                "trade_date": trade_date.isoformat(),
                "group": "国債利回り",
                "name": f"{name} 10年国債",
                "value": value,
                "unit": "%",
                "change": change,
                "updated": stamp,
            }
        )

    return rows


def parse_policy(text, today=None):
    """楽天証券の画面から政策金利を4件だけ抜く。

    1行はこうなっている:

        日本 無担保コール翌日物\t0.977\t2026/08/10

    値や日付が "--" の日がある。値が無ければ記録しない。
    """
    today = today or date.today()
    rows, seen = [], set()

    for line in text.split("\n"):
        c = _cells(line)
        if len(c) < 2:
            continue

        name = c[0]
        if name not in POLICY_RATES or name in seen:
            continue

        value = _number(c[1])
        if value is None:
            # "--" の日。値が無いものは書かない
            continue

        stamp = c[2] if len(c) > 2 else ""
        m = SLASH_DATE.match(stamp)
        if m:
            trade_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            # 日付が出ていない項目がある（FF金利など）。取得日を使う
            trade_date = today

        seen.add(name)
        rows.append(
            {
                "trade_date": trade_date.isoformat(),
                "group": "政策金利",
                "name": name,
                "value": value,
                "unit": "%",
                "change": None,
                "updated": stamp,
            }
        )

    return rows
