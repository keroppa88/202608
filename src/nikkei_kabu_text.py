"""日経の国内株式指標ページの表示テキストから数値を取り出す（SPEC §4E）。

https://www.nikkei.com/markets/kabu/japanidx/

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

表はどれも同じ形をしている。

    表題（時価情報／純資産倍率／株価収益率 …）
    項目名  列名  列名 …          ← 見出し
    項目名                         ← 1〜2行に折り返すことがある
    値  値 …                      ← 列の数だけ続く

列名と最初の項目名は、どちらも「項目名」の後ろに文字の行として続くので
見た目では区別できない。そこで**最初の値のまとまりの個数**を列数とみなす。
値が3つ並べば3列、1つなら1列。残った行が最初の項目名になる。

「時価総額」と「(普通株式ベース)」のように項目名が2行に分かれるため、
値が現れるまでの行はつないで項目名とする。
"""

import re
from datetime import date

# 「国内の株式指標・東証（10日）」。日だけで年月がない
HEADING = re.compile(r"国内の株式指標・(.+?)（(\d{1,2})日）")

# 表の見出しの先頭。この行の続きが列名になる
COLUMN_HEAD = "項目名"

# 値として認める形。数値のあとに単位が付く。`--` `－` は値なし
VALUE = re.compile(r"^-?[\d,]+\.?\d*\s*(億円|百万円|百万株|万株|円|倍|％|%)?$")
NO_VALUE = ("--", "-", "－", "―")

# 表題として扱う行。ここで表が切り替わる。
# 前方一致ではなく完全一致で見る。「純資産倍率」は列名にも同じ語が現れ、
# 前方一致だと表の途中で節が切り替わったと誤判定するため
SECTIONS = (
    "時価情報",
    "純資産倍率（連結決算ベース）",
    "株価収益率（連結決算ベース）",
    "株式益回り（連結決算ベース）",
    "平均配当利回り（売買単位換算）",
    "売買高・売買代金・騰落銘柄数",
)

# 表の外にある行。値の並びに混ざらないよう落とす
NOISE = ("データ説明", "注記", "続きを読む")


class ExtractError(Exception):
    pass


def _split_value(text):
    """「13,625,213億円」を (13625213.0, "億円") に分ける。値なしは (None, "")。"""
    text = text.strip()
    if text in NO_VALUE:
        return None, ""
    m = VALUE.match(text)
    if not m:
        return None, ""
    unit = m.group(1) or ""
    return float(text[: len(text) - len(unit)].strip().replace(",", "")), unit


def _maybe_date(year, month, day):
    """存在しない日付なら None。31日のない月などを踏まないため。"""
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_date(text, today=None):
    """見出しの「（10日）」と市場名を返す。年月は実行日から補う。"""
    today = today or date.today()
    m = HEADING.search(text)
    if not m:
        raise ExtractError("見出し「国内の株式指標・…（◯日）」が見つからない")

    market, day = m.group(1), int(m.group(2))

    # まず当月。実行日より後になる、または当月に存在しない日なら前月とみなす
    # （9月1日に「31日」と出ていれば 8月31日。9月31日を作ろうとすると落ちる）
    current = _maybe_date(today.year, today.month, day)
    if current and current <= today:
        return current, market

    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    previous = _maybe_date(year, month, day)
    if previous:
        return previous, market
    raise ExtractError(f"見出しの日付を解釈できない（{day}日 / 実行日 {today}）")


def parse(text, today=None):
    """[{trade_date, market, section, item, column, value, unit}] を返す。"""
    trade_date, market = find_date(text, today)
    # ブラウザで取ると表のセルがタブ区切りの1行になる。1セル1行に開く
    lines = [c.strip() for ln in text.split("\n") for c in ln.split("\t") if c.strip()]

    try:
        start = next(i for i, ln in enumerate(lines) if HEADING.search(ln))
    except StopIteration:
        raise ExtractError("見出しの行が見つからない") from None

    rows = []
    section = None
    columns = []      # 列名。最初の値のまとまりの個数で決まる
    pending = []      # 列名か最初の項目名か、まだ分からない行
    name_parts = []   # 項目名。2行に折り返すことがある
    values = []       # 現在の項目について読んだ値

    def emit():
        if not name_parts or not values:
            return
        item = "".join(name_parts)
        for i, (value, unit) in enumerate(values):
            rows.append(
                {
                    "trade_date": trade_date,
                    "market": market,
                    "section": section,
                    "item": item,
                    "column": columns[i] if i < len(columns) else "",
                    "value": value,
                    "unit": unit,
                }
            )

    def settle_header():
        """列数が決まった時点で、pending を列名と最初の項目名に分ける。"""
        nonlocal columns, pending, name_parts
        n = len(values)
        columns = pending[:n]
        name_parts = pending[n:]
        pending = []

    for ln in lines[start + 1 :]:
        if ln in NOISE:
            continue

        if ln in SECTIONS:
            # 表の最後の項目は、次の節に入って初めて終わりが分かる
            if not columns and values:
                settle_header()
            emit()
            section, columns, pending, name_parts, values = ln, [], [], [], []
            continue
        if section is None:
            continue

        if ln == COLUMN_HEAD:
            if not columns and values:
                settle_header()
            emit()
            columns, pending, name_parts, values = [], [], [], []
            continue

        value, unit = _split_value(ln)
        is_value = value is not None or ln in NO_VALUE

        if is_value:
            values.append((value, unit))
            if columns and len(values) >= len(columns):
                emit()
                name_parts, values = [], []
            continue

        # ここから文字の行
        if not columns:
            if values:
                # 最初のまとまりが終わった。個数が列数
                settle_header()
                emit()
                values = []
                name_parts = [ln]
            else:
                pending.append(ln)
            continue

        if values:  # 値の途中で名前が来たら、その項目はそこで終わり
            emit()
            name_parts, values = [], []
        name_parts.append(ln)

    if not columns and values:
        settle_header()
    emit()

    if not rows:
        raise ExtractError("値の行が1件も取れない")
    return rows
