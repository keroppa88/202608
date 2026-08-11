"""CNN の Fear & Greed Index の表示テキストから日付と値を取り出す（SPEC §4J）。

https://edition.cnn.com/markets/fear-and-greed

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

画面はこの並びになっている。

    Overview
    Timeline
    65                ← 現在の値
    Previous close
    64
    1 week ago
    59
    1 month ago
    46
    1 year ago
    57
    Last updated Aug 11 at 8:28:31 AM ET

「Previous close」の直前の行が現在の値。ページには年が出ないので実行日から補う。
"""

import re
from datetime import date

CURRENT_MARK = "Previous close"

# 「Last updated Aug 11 at 8:28:31 AM ET」
UPDATED = re.compile(r"Last updated\s+([A-Z][a-z]{2})\s+(\d{1,2})\b")

MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    )
}

VALUE = re.compile(r"^\d{1,3}$")


class ExtractError(Exception):
    pass


def _maybe_date(year, month, day):
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_date(text, today=None):
    """「Last updated Aug 11 …」から日付を返す。年は実行日から補う。"""
    today = today or date.today()
    m = UPDATED.search(text)
    if not m:
        raise ExtractError("「Last updated ◯◯ ◯日」が見つからない")
    month, day = MONTHS[m.group(1)], int(m.group(2))

    # まず当年。実行日より先になるなら前年とみなす（年末年始のずれ）
    current = _maybe_date(today.year, month, day)
    if current and current <= today:
        return current
    previous = _maybe_date(today.year - 1, month, day)
    if previous:
        return previous
    raise ExtractError(f"日付を解釈できない（{month}/{day} / 実行日 {today}）")


def parse(text, today=None):
    """{trade_date, value} を返す。"""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    value = None
    for i, line in enumerate(lines):
        if line == CURRENT_MARK and i > 0 and VALUE.match(lines[i - 1]):
            value = int(lines[i - 1])
            break
    if value is None:
        raise ExtractError("「Previous close」の直前に値が見つからない")
    if not 0 <= value <= 100:
        raise ExtractError(f"値が範囲外（{value}）")

    return {"trade_date": find_date(text, today), "value": value}
