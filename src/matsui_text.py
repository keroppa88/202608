"""松井証券の投資指標ページの表示テキストから数値を取り出す（SPEC §4G）。

https://www.matsui.co.jp/market/stock/netstock-info/

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

3つの大区分があり、それぞれの直後に日付、その下に表が並ぶ。
表はタブ区切りの1行になっている。

    取引動向(松井証券店内)     ← 大区分
    8/7(金)                    ← 日付。年は無い
    市場別株式売買代金          ← 表題
     → 東証 → 内グロース市場    ← 見出し。先頭のセルが空
    売り代金 (億円) → 2,972.63 → 28.57
    東証は東証プライム…です。   ← 注記。表の外

値には単位や注記が付くことがある。

    22.740倍         → 22.740 と単位「倍」
    99,935(買い)     → 99935 と注記「買い」
"""

import re
from datetime import date

# 大区分。完全一致で見る。「投資指標(松井証券店内)」はページ表題や
# ご注意の文中にも現れるため、大区分として拾ってはいけない
GROUPS = (
    "取引動向(松井証券店内)",
    "信用取引指標(松井証券店内)",
    "先物指標(松井証券店内)",
)

# 「8/7(金)」。年はページに出ないので実行日から補う
DATE = re.compile(r"^(\d{1,2})/(\d{1,2})\(.\)$")

# 「2,972.63」「22.740倍」「99,935(買い)」「-366」
VALUE = re.compile(
    r"^(-?[\d,]+(?:\.\d+)?)\s*([^\d\s(（)）]*)\s*(?:[(（]([^)）]*)[)）])?$"
)


class ExtractError(Exception):
    pass


def _blank(cell):
    """空欄。全角スペースや不可視スペースで埋められていることがある。"""
    return not cell.strip().strip(" 　")


def _split_value(cell):
    """セルを (値, 単位, 注記) に分ける。値として読めなければ (None, "", 生の文字)。"""
    text = cell.strip().strip(" 　").strip()
    if not text:
        return None, "", ""
    m = VALUE.match(text)
    if not m:
        return None, "", text
    return float(m.group(1).replace(",", "")), m.group(2) or "", m.group(3) or ""


def _maybe_date(year, month, day):
    """存在しない日付なら None。2/30 のような表記を踏まないため。"""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _resolve(month, day, today):
    """「8/7」に年を補う。実行日より後になるなら前年とみなす。"""
    current = _maybe_date(today.year, month, day)
    if current and current <= today:
        return current
    previous = _maybe_date(today.year - 1, month, day)
    if previous:
        return previous
    raise ExtractError(f"日付を解釈できない（{month}/{day} / 実行日 {today}）")


def parse(text, today=None):
    """[{trade_date, group, section, item, column, value, unit, note}] を返す。"""
    today = today or date.today()
    lines = text.split("\n")

    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() in GROUPS)
    except StopIteration:
        raise ExtractError("大区分の見出しが1つも見つからない") from None

    rows = []
    group = section = trade_date = None
    columns = []

    for raw in lines[start:]:
        line = raw.rstrip("\n")
        if not line.strip():
            continue

        if "\t" not in line:
            plain = line.strip()
            if plain in GROUPS:
                group, section, columns = plain, None, []
                continue
            m = DATE.match(plain)
            if m:
                trade_date = _resolve(int(m.group(1)), int(m.group(2)), today)
                continue
            if group is None or plain.endswith("。"):
                continue  # 表の外の注記
            section, columns = plain, []  # 表題
            continue

        cells = line.split("\t")
        if _blank(cells[0]):
            # 先頭のセルが空なら見出し行。残りが列名
            columns = [c.strip() for c in cells[1:]]
            continue

        if group is None or section is None or trade_date is None:
            continue
        item = cells[0].strip()
        for i, cell in enumerate(cells[1:]):
            value, unit, note = _split_value(cell)
            if value is None and not note:
                continue  # 空欄。列を埋めるためだけの升目
            rows.append(
                {
                    "trade_date": trade_date,
                    "group": group,
                    "section": section,
                    "item": item,
                    "column": columns[i] if i < len(columns) else "",
                    "value": value,
                    "unit": unit,
                    "note": note,
                }
            )

    if not rows:
        raise ExtractError("値の行が1件も取れない")
    return rows
