"""CNBC のセクター一覧の表示テキストから S&P500 セクター指数を取り出す（SPEC §4I）。

https://www.cnbc.com/markets/sectors/

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

表はこの形。銘柄名が1行、その次の行に値がタブ区切りで並ぶ。
値の行は先頭のセル（シンボル欄）が空なのでタブで始まる。

    SYMBOL → PRICE → CHANGE → %CHANGE → LOW → HIGH → PREVIOUS CLOSE
    HEALTH
     → 1,962.94 → +32.35 → +1.68 → 1,930.47 → 1,962.96 → 1,930.59

始値は出ない。高値・安値・終値・前日終値が取れる。
"""

import re

HEADER = "SYMBOL"

# CNBC の表記と、これまで Yahoo で使っていたシンボル・名称の対応。
# 値は同じ S&P500 セクター指数なので、同じシンボルに入れれば履歴が続く
SECTORS = {
    "TECHNOLOGY": ("^SP500-45", "S&P500 IT"),
    "FINANCIALS": ("^SP500-40", "S&P500 金融"),
    "HEALTH": ("^SP500-35", "S&P500 ヘルスケア"),
    "INDUSTRIALS": ("^SP500-20", "S&P500 資本財"),
    "ENERGY": ("^GSPE", "S&P500 エネルギー"),
    "CONS DISC": ("^SP500-25", "S&P500 一般消費財・サービス"),
    "CONS STPL": ("^SP500-30", "S&P500 生活必需品"),
    "MATERIALS": ("^SP500-15", "S&P500 素材"),
    "COMMUNICATION SVS": ("^SP500-50", "S&P500 電気通信"),
    "UTILITIES": ("^SP500-55", "S&P500 公益"),
    "REAL ESTATE": ("^SP500-60", "S&P500 不動産"),
}

NUMBER = re.compile(r"^[+\-]?[\d,]+\.?\d*$")


class ExtractError(Exception):
    pass


def _num(text):
    text = text.strip().replace(",", "").replace("%", "")
    return float(text) if NUMBER.match(text) else None


def parse(text):
    """[{symbol, name, close, change, change_pct, low, high, prev_close}] を返す。"""
    lines = text.split("\n")
    rows, pending = [], None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(HEADER):
            continue

        if stripped in SECTORS:
            pending = stripped
            continue

        if pending is None or "\t" not in line:
            continue

        values = [_num(c) for c in line.split("\t") if c.strip()]
        if len(values) < 6 or any(v is None for v in values[:6]):
            pending = None
            continue

        symbol, name = SECTORS[pending]
        close, change, change_pct, low, high, prev_close = values[:6]
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "close": close,
                "change": change,
                "change_pct": change_pct,
                "low": low,
                "high": high,
                "prev_close": prev_close,
            }
        )
        pending = None

    if not rows:
        raise ExtractError("セクターの行が1件も取れない")
    return rows
