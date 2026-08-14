"""読売333のページの表示テキストから指数値を取り出す。

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない。

画面にはこの並びで出ている。

    読売株価指数
    2026.08.14      取引日
    54083.88円      終値
    +255.29         前日比
    +0.47%          前日比（％）

四本値は出ていない。終値と前日比だけを記録する。
"""

import re

DATE = re.compile(r"^(\d{4})[./-](\d{1,2})[./-](\d{1,2})$")
VALUE = re.compile(r"^([\d,]+\.?\d*)円$")
CHANGE = re.compile(r"^([+-][\d,]+\.?\d*)$")
CHANGE_PCT = re.compile(r"^([+-][\d,]+\.?\d*)%$")

NAME = "読売333"


class ExtractError(Exception):
    pass


def _num(text):
    return float(text.replace(",", ""))


def parse(text):
    """{trade_date, name, close, change, change_pct} を返す。

    「日付の行のすぐ下に『数字円』の行」という並びで拾う。
    ページには他にも数字が並ぶが、この2行が続く場所は指数値のところだけ。
    """
    lines = [ln.strip() for ln in text.split("\n")]

    for i, ln in enumerate(lines):
        m = DATE.match(ln)
        if not m or i + 1 >= len(lines):
            continue
        v = VALUE.match(lines[i + 1])
        if not v:
            continue

        y, mo, d = (int(g) for g in m.groups())
        if not (2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
            continue

        # 前日比はこの下に続く。無ければ空のままにする
        change = change_pct = None
        for ln2 in lines[i + 2:i + 5]:
            if change is None and CHANGE.match(ln2):
                change = _num(CHANGE.match(ln2).group(1))
            elif change_pct is None and CHANGE_PCT.match(ln2):
                change_pct = _num(CHANGE_PCT.match(ln2).group(1))

        return {
            "trade_date": f"{y:04d}-{mo:02d}-{d:02d}",
            "name": NAME,
            "close": _num(v.group(1)),
            "change": change,
            "change_pct": change_pct,
        }

    raise ExtractError("日付と指数値の並びが見つからない")
