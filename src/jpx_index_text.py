"""JPX の株価指数ページの表示テキストから指数値を取り出す（SPEC §4D）。

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

表は次の並びで、タブ区切りの1行になっている。

    指数名 → 現在値 → 前日比 → 前日比% → 始値 → 高値 → 安値 → （グラフ列）

始値・高値・安値が `--` の指数は、現在値だけが公表されている。
"""

import re

# 見出し行・区切り行。データではない
SKIP_LINES = ("指数名", "先頭に戻る")

# 値のない欄。ハイフン1〜2個で表される
EMPTY = ("--", "-", "")

NUMBER = re.compile(r"^-?[\d,]+\.?\d*$")


class ExtractError(Exception):
    pass


def _num(text):
    text = text.strip()
    return None if text in EMPTY else float(text.replace(",", ""))


def parse(text):
    """指数ごとの値を返す。名前のない行は数を数えて別に返す。

    戻り値: (rows, skipped)
        rows    … [{name, close, change, change_pct, open, high, low}]
        skipped … 名前が読めなかった行数
    """
    rows, seen, skipped = [], set(), 0

    for line in text.split("\n"):
        if not line.strip() or line.strip().startswith(SKIP_LINES):
            continue
        cells = line.split("\t")
        if len(cells) < 4:
            continue

        name = cells[0].strip()
        has_close = bool(NUMBER.match(cells[1].strip()))
        # 前日比が数値なら、指数名や現在値が欠けていてもデータ行のなれの果て
        looks_like_row = has_close or NUMBER.match(cells[2].strip().replace("+", ""))

        if not name or not has_close:
            # ページ側で指数名や現在値が表示されていない行。値だけ取っても意味がないので
            # 捨てるが、黙って減らすと取りこぼしに気づけない（SPEC §2.4）
            if looks_like_row:
                skipped += 1
            continue
        if name in seen:
            continue  # 同じ指数が複数の節に載っている。最初の1件を採る
        seen.add(name)

        def cell(i):
            return _num(cells[i]) if i < len(cells) else None

        rows.append(
            {
                "name": name,
                "close": cell(1),
                "change": cell(2),
                "change_pct": _num(cells[3].replace("%", "")) if len(cells) > 3 else None,
                "open": cell(4),
                "high": cell(5),
                "low": cell(6),
            }
        )

    if not rows:
        raise ExtractError("指数の行が1件も取れない")
    return rows, skipped
