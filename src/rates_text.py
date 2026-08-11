"""金利ページの表示テキストから利回りと政策金利を取り出す（SPEC §4H）。

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

3つのページを扱う。どれも表がタブ区切りの1行になっている。

SBI（日本・米国の国債）
    債券 → 現在値・年利回り → 前日比 → 前日比率 → 更新日時
    日本国債10年 → 2.822 → +0.012 → --％ → 26/08/11 02:25

楽天（その他の国の国債）
    指標 → 年利回り → 前日比 → 更新日時
    イギリス10年国債 → 5.041 → +0.052 → 08/11 18:59

楽天（政策金利）
    指標 → 政策金利 → 更新日時
    日本 無担保コール翌日物 → 0.977 → 2026/08/10

値は終値のみで四本値は無い。更新日時は配信元の文字をそのまま持つ。
書式がページごとに違ううえ（年の有無・時差表記）、日本国債と米国債で
時間帯も違うため、日付として解釈し直さない。
"""

import re

# 見出し行の先頭。ここから下がデータ
HEADERS = ("債券", "指標")

# 値なし
EMPTY = ("--", "-", "―", "")

NUMBER = re.compile(r"^[+\-±]?[\d,]+\.?\d*$")


class ExtractError(Exception):
    pass


def _num(text):
    text = text.strip().replace(",", "").replace("％", "").replace("%", "")
    if text in EMPTY:
        return None
    text = text.lstrip("±")
    return float(text) if NUMBER.match(text) else None


def _rows(text, columns):
    """見出し行を見つけ、その下のタブ行を列数ぶん読む。"""
    out = []
    seen_header = False
    for line in text.split("\n"):
        cells = [c.strip() for c in line.split("\t")]
        if len(cells) < 2:
            continue
        if not seen_header:
            if cells[0] in HEADERS and len(cells) >= len(columns) + 1:
                seen_header = True
            continue
        name = cells[0]
        if not name or name in EMPTY or " " == name:
            break  # 表の終わり（提供元の注記など）
        if len(cells) < len(columns) + 1:
            break
        out.append((name, cells[1 : len(columns) + 1]))
    if not out:
        raise ExtractError("表の行が1件も取れない")
    return out


def bonds_sbi(text):
    """SBIの債券表。[{name, value, change, change_pct, updated}]"""
    rows = []
    for name, v in _rows(text, ["値", "前日比", "前日比率", "更新日時"]):
        rows.append(
            {
                "name": name,
                "value": _num(v[0]),
                "change": _num(v[1]),
                "change_pct": _num(v[2]),
                "updated": v[3],
            }
        )
    return rows


def bonds_rakuten(text):
    """楽天の債券表。[{name, value, change, updated}]"""
    rows = []
    for name, v in _rows(text, ["年利回り", "前日比", "更新日時"]):
        rows.append(
            {
                "name": name,
                "value": _num(v[0]),
                "change": _num(v[1]),
                "change_pct": None,
                "updated": v[2],
            }
        )
    return rows


def policy_rates(text):
    """楽天の政策金利表。[{name, value, updated}]"""
    rows = []
    for name, v in _rows(text, ["政策金利", "更新日時"]):
        rows.append(
            {
                "name": re.sub(r"[\s　]+", " ", name),
                "value": _num(v[0]),
                "change": None,
                "change_pct": None,
                "updated": v[1] if v[1] not in EMPTY else "",
            }
        )
    return rows
