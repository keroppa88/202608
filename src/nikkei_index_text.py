"""日経の指数ページの表示テキストから数値を取り出す（SPEC §4C）。

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
タグ・クラス名・属性は参照しない（SPEC §2.2）。

手がかりは人が画面を見て使うものと同じ。

    ・「始値」で始まる行に、値と時刻がタブ区切りで並んでいる
    ・指数一覧は「名称 / 指数値 / 前日比 / データ日付」の4行1組
    ・寄与度は「セクター名」の次の行が「◯◯円」になっている
"""

import re
from datetime import date, datetime

# 「2026年8月10日(月)」 サマリーページの日付
DATE_JP = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\([月火水木金土日]\)$")

# 「2026.08.10(15:30)」 プロフィルページの日時
DATE_DOT = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})\((\d{1,2}:\d{2}|終値|\*?大引)\)")

# 「08.10(終値)」 指数一覧の日付。年がないので実行日から補う
DATE_MD = re.compile(r"^(\d{2})\.(\d{2})\((.+)\)$")

# 「始値\t65,905.10\t09:00」
OHLC_ROW = re.compile(r"^(始値|高値|安値|除数)\t([\d,.]+)\t?(\d{1,2}:\d{2})?")

NUMBER = re.compile(r"^-?[\d,]+\.?\d*$")


class ExtractError(Exception):
    pass


def _num(s):
    return float(s.replace(",", "").replace("円", "").replace("%", "").replace("倍", ""))


def _lines(text):
    return [ln.rstrip() for ln in text.split("\n") if ln.strip()]


def _md_to_date(mm, dd, today):
    """月日しかない日付を、実行日を基準に年を補って返す。"""
    year = today.year
    d = date(year, int(mm), int(dd))
    if (d - today).days > 180:  # 先の日付になるなら前年
        d = date(year - 1, int(mm), int(dd))
    return d


# --------------------------------------------------------------------------
# 日経平均 サマリーページ
# --------------------------------------------------------------------------

def parse_summary(text):
    """四本値・時刻・詳細指標をまとめて返す。"""
    lines = _lines(text)

    trade_date = None
    for ln in lines:
        m = DATE_JP.match(ln.strip())
        if m:
            trade_date = date(*(int(g) for g in m.groups()))
            break
    if not trade_date:
        raise ExtractError("日付の行が見つからない")

    ohlc, times, divisor = {}, {}, None
    for ln in lines:
        m = OHLC_ROW.match(ln)
        if not m:
            continue
        label, value, at = m.group(1), _num(m.group(2)), m.group(3)
        if label == "除数":
            divisor = value
        else:
            key = {"始値": "open", "高値": "high", "安値": "low"}[label]
            ohlc[key] = value
            if at:
                times[key] = at

    # 終値は「前日比の行」の直前にある数値の行
    close = None
    for i, ln in enumerate(lines):
        if re.match(r"^[+-][\d.]+% [+-][\d,.]+$", ln.strip()) and i:
            prev = lines[i - 1].strip()
            if NUMBER.match(prev):
                close = _num(prev)
                break
    if close is None or len(ohlc) != 3:
        raise ExtractError("四本値が揃わない")

    return {
        "trade_date": trade_date,
        "ohlc": {**ohlc, "close": close},
        "times": times,
        "detail": _summary_detail(lines, divisor),
    }


def _pairs_after(lines, header, stop_at):
    """見出しの後ろにある「名前 / 値」の並びを拾う。"""
    out = []
    try:
        i = lines.index(header) + 1
    except ValueError:
        return out
    while i < len(lines) - 1:
        name, value = lines[i].strip(), lines[i + 1].strip()
        if any(name.startswith(s) for s in stop_at):
            break
        # グラフの目盛りは数値だけの行なので飛ばす
        if NUMBER.match(name):
            i += 1
            continue
        if re.match(r"^-?[\d,.]+(%|円)$", value):
            out.append((name, _num(value)))
            i += 2
        else:
            i += 1
    return out


def _summary_detail(lines, divisor):
    """除数・PER・PBR・利回り・規模・騰落・ウェート・寄与度をまとめて返す。"""
    rows = []

    if divisor is not None:
        rows.append(("基本", "除数", "", divisor, ""))

    # 「配当利回り / 単純平均 / 1.62% / 指数ベース / 1.37%」の形。
    # 動的データが未反映だと「-%」「-倍」になるため、その項目だけ飛ばす。
    labels = {
        "配当利回り": ("配当利回り", "%"),
        "株価収益率(PER)": ("PER", "倍"),
        "株価純資産倍率(PBR)": ("PBR", "倍"),
    }
    for i, ln in enumerate(lines):
        key = labels.get(ln.strip())
        if not key:
            continue
        name, unit = key
        for j in range(i + 1, min(i + 6, len(lines) - 1)):
            sub = lines[j].strip()
            if sub in ("単純平均", "加重平均", "指数ベース"):
                value = lines[j + 1].strip()
                if re.match(r"^-?[\d,.]+(?:%|倍)$", value):
                    rows.append((name, name, sub, _num(value), unit))

    # 「時価総額合計 / 1,049.08 兆円 / (対市場占有率 77.00%)」の形
    for i, ln in enumerate(lines):
        if ln.strip() in ("時価総額合計", "売買代金合計") and i + 2 < len(lines):
            name = ln.strip()
            m = re.match(r"^([\d,.]+)\s*(兆円|億円)$", lines[i + 1].strip())
            if m:
                rows.append(("規模", name, "", _num(m.group(1)), m.group(2)))
            m = re.search(r"対市場占有率\s*([\d.]+)%", lines[i + 2])
            if m:
                rows.append(("規模", name, "対市場占有率", float(m.group(1)), "%"))

    # 「上昇： / 121銘柄」の形
    for i, ln in enumerate(lines):
        m = re.match(r"^(上昇|下落|変わらず)：$", ln.strip())
        if m and i + 1 < len(lines):
            v = re.match(r"^([\d,]+)銘柄$", lines[i + 1].strip())
            if v:
                rows.append(("騰落銘柄数", m.group(1), "", _num(v.group(1)), "銘柄"))

    # 上昇確率
    for i, ln in enumerate(lines):
        m = re.match(r"^上昇確率([\d.]+)%$", ln.strip())
        if m:
            rows.append(("上昇確率", "上昇確率", "", float(m.group(1)), "%"))
            if i + 1 < len(lines):
                w = re.match(r"^（(\d+)勝(\d+)負(\d+)分）$", lines[i + 1].strip())
                if w:
                    for label, val in zip(("勝", "負", "分"), w.groups()):
                        rows.append(("上昇確率", label, "", float(val), "回"))

    # ウェート上位10銘柄（タブ区切りの表）
    for ln in lines:
        cells = ln.split("\t")
        if len(cells) == 7 and cells[0].strip().isdigit():
            rank, code, short, _full, sector, industry, weight = (
                c.strip() for c in cells
            )
            rows.append(
                ("ウェート上位", f"{rank}. {code} {short}", f"{sector}/{industry}",
                 _num(weight), "%")
            )

    stop = ("セクター別", "指数をもっと", "ライセンス")
    for name, value in _pairs_after(lines, "セクター別ウェート", stop):
        rows.append(("セクター別ウェート", name, "", value, "%"))
    for name, value in _pairs_after(lines, "セクター別騰落寄与度", stop):
        rows.append(("セクター別寄与度", name, "", value, "円"))

    return rows


# --------------------------------------------------------------------------
# プロフィルページ（日経VI・日経半導体株指数）
# --------------------------------------------------------------------------

def parse_profile(text):
    """指数名・四本値・時刻を返す。"""
    lines = _lines(text)

    at = None
    for i, ln in enumerate(lines):
        m = DATE_DOT.search(ln)
        if m:
            at = i
            trade_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            break
    if at is None:
        raise ExtractError("日時の行が見つからない")

    # 日時の行の2つ上が指数名、1つ上が指数値
    if at < 2:
        raise ExtractError("指数名・指数値の行がない")
    name = lines[at - 2].strip()
    if not NUMBER.match(lines[at - 1].strip()):
        raise ExtractError("指数値が数値でない")
    close = _num(lines[at - 1])

    ohlc, times = {}, {}
    for ln in lines[at:]:
        m = OHLC_ROW.match(ln)
        if m and m.group(1) != "除数":
            key = {"始値": "open", "高値": "high", "安値": "low"}[m.group(1)]
            ohlc[key] = _num(m.group(2))
            if m.group(3):
                times[key] = m.group(3)
    if len(ohlc) != 3:
        raise ExtractError("四本値が揃わない")

    return {
        "name": name,
        "trade_date": trade_date,
        "ohlc": {**ohlc, "close": close},
        "times": times,
    }


# --------------------------------------------------------------------------
# 指数一覧ページ
# --------------------------------------------------------------------------

def parse_index_list(text, wanted, today=None, strict=True):
    """一覧から指定の指数の大引け値を拾う。「名称 / 値 / 前日比 / 日付」の4行1組。

    strict=False なら一部の指数が見つからなくても、見つかったものを返す。
    """
    today = today or date.today()
    lines = _lines(text)
    found = {}

    for i, ln in enumerate(lines):
        name = ln.strip()
        if name not in wanted or i + 3 >= len(lines):
            continue
        value, _chg, when = (lines[i + j].strip() for j in (1, 2, 3))
        if not NUMBER.match(value):
            continue
        m = DATE_MD.match(when)
        if not m:
            continue
        found[name] = {
            "trade_date": _md_to_date(m.group(1), m.group(2), today),
            "close": _num(value),
            "note": m.group(3),
        }

    missing = [w for w in wanted if w not in found]
    if strict and missing:
        raise ExtractError(f"一覧に見つからない: {', '.join(missing)}")
    return found
