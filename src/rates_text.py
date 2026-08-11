"""SMBC日興の金利ページの表示テキストから利回りと政策金利を取り出す（SPEC §4H）。

https://www.smbcnikko.co.jp/market/interest/

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

3つの節があり、どれも「名前 → 日付 → …」の並びになっている。

    国債利回り（終値）
    日本国債10年
    08/10 （終値）      ← 日付。年は出ない
    利回り
    2.805%
    前日比
    (+0.010)

    国債先物（15分遅れ）
    日本 長期国債先物
    08/10 15:02 （15分遅れ）
    価格
    126.90円
    前日比
    (-0.08)

    政策金利
    日本 無担保ｺｰﾙ翌日物
    08/11
    1.00%

**日付は項目ごとに違う**（市場によって最終取引日がずれる）。
その項目の日付をそのまま取引日とする。

政策金利の節には「日足 週足 月足」「表示」といった操作用の行が混ざるが、
日付の行の直前だけを名前として拾うので巻き込まれない。
"""

import re
from datetime import date

SECTIONS = {
    "国債利回り（終値）": "国債利回り",
    "国債先物（15分遅れ）": "国債先物",
    "政策金利": "政策金利",
}

# 「08/10 （終値）」「08/10 15:02 （15分遅れ）」「08/11」
DATED = re.compile(r"^(\d{1,2})/(\d{1,2})(?:\s+\d{1,2}:\d{2})?(?:\s*（.+?）)?$")

# 「2.805%」「126.90円」「8.47%」
VALUE = re.compile(r"^(-?[\d,]+\.?\d*)\s*(%|円)?$")

# 「(+0.010)」「(-0.08)」
CHANGE = re.compile(r"^[（(]([+\-±]?[\d,]+\.?\d*)[）)]$")

# 値の前に置かれる見出し。飛ばす
LABELS = ("利回り", "価格", "前日比")


class ExtractError(Exception):
    pass


def _num(text):
    text = text.strip().replace(",", "").lstrip("±")
    try:
        return float(text)
    except ValueError:
        return None


def _maybe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve(month, day, today):
    """ページに年が出ないので実行日から補う。実行日より先なら前年。"""
    current = _maybe_date(today.year, month, day)
    if current and current <= today:
        return current
    previous = _maybe_date(today.year - 1, month, day)
    if previous:
        return previous
    raise ExtractError(f"日付を解釈できない（{month}/{day} / 実行日 {today}）")


def parse(text, today=None):
    """[{trade_date, group, name, value, unit, change, updated}] を返す。"""
    today = today or date.today()
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    rows = []
    group = None
    for i, line in enumerate(lines):
        if line in SECTIONS:
            group = SECTIONS[line]
            continue
        if group is None:
            continue

        m = DATED.match(line)
        if not m or i == 0:
            continue
        name = lines[i - 1]
        if name in SECTIONS or name in LABELS:
            continue

        # 日付の後ろから、見出しを飛ばしつつ値と前日比を拾う
        value = unit = None
        change = None
        for follow in lines[i + 1 : i + 6]:
            if follow in LABELS:
                continue
            if value is None:
                v = VALUE.match(follow)
                if not v:
                    break
                value, unit = _num(v.group(1)), v.group(2) or ""
                continue
            c = CHANGE.match(follow)
            if c:
                change = _num(c.group(1))
            break

        if value is None:
            continue

        rows.append(
            {
                "trade_date": _resolve(int(m.group(1)), int(m.group(2)), today),
                "group": group,
                "name": name,
                "value": value,
                "unit": unit,
                "change": change,
                # 「08/10 15:02 （15分遅れ）」のような但し書きをそのまま残す
                "updated": line,
            }
        )

    if not rows:
        raise ExtractError("金利の行が1件も取れない")
    return rows
