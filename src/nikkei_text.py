"""日経の記事ページの表示テキストから、題名・記事年月日・本文を取り出す。

入力は「画面に見えている文字を丸ごと写したテキスト」だけ。
HTML のタグ・クラス名・属性は一切参照しない（SPEC §2.2）。

手がかりにするのは、人が画面を見て判断するのと同じもの。

    ・日付は「2026年8月10日 15:48」という形で1行だけ現れる
    ・題名はその直前にある、いちばん長い行
    ・本文はその下に続く長い行の連なり
"""

import re
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# 「2026年8月10日 15:48」。記事の掲載日時はこの形で1行に出る
DATE_LINE = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})$")

# 本文とみなす行の最短の長さ。共有ボタンや見出しは これより短い
BODY_MIN = 40

# 本文の終わりを示す行。ここまでを本文に含める
END_MARKERS = ("〔日経QUICKニュース（NQN）〕",)

# 記事本文ではないと分かる行。長さに関係なく飛ばす（本文は終わらせない）
NOT_BODY = (
    "記事利用サービス",
    "転載・複製",
    "リンク先をご覧ください",
    "詳しくはこちら",
    "記事を印刷",
    "メールで送る",
    "リンクをコピー",
)

# 本文の後ろに続く、記事ではない行
AFTER_BODY = (
    "アプリで開く",
    "すべての記事が読み放題",
    "有料会員",
    "無料会員",
    "ログインする",
    "日経電子版の記事を学習したAI",
    "関連トピック",
    "セレクション",
)


class ExtractError(Exception):
    pass


def _lines(text):
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def parse(text):
    """題名・掲載日時・本文を返す。判断できなければ例外にする（空を返さない）。"""
    lines = _lines(text)

    # 1) 掲載日時の行を探す
    at = None
    for i, ln in enumerate(lines):
        m = DATE_LINE.match(ln)
        if m:
            at = i
            y, mo, d, h, mi = (int(g) for g in m.groups())
            published = datetime(y, mo, d, h, mi, tzinfo=JST)
            break
    if at is None:
        raise ExtractError("掲載日時の行が見つからない")

    # 2) 題名は日付の少し上にある。周辺でいちばん長い行を採る
    #    （直前はカテゴリ名などの短い行になることがある）
    above = [ln for ln in lines[max(0, at - 4) : at] if len(ln) > 8]
    if not above:
        raise ExtractError("題名の行が見つからない")
    headline = max(above, key=len)

    # 3) 本文は日付より下。長い行が本文、短い行は共有ボタンなどの飾り
    body = []
    for ln in lines[at + 1 :]:
        if any(ln.startswith(m) for m in END_MARKERS):
            body.append(ln)
            break
        if any(k in ln for k in NOT_BODY):
            continue
        if any(k in ln for k in AFTER_BODY):
            if body:
                break
            continue
        if len(ln) >= BODY_MIN:
            body.append(ln)
        elif body:
            # 本文が始まった後の短い行は、記事末尾の署名などの可能性がある
            if ln.startswith("〔") or ln.startswith("（"):
                body.append(ln)
    if not body:
        raise ExtractError("本文が取れない")

    return {
        "headline": headline,
        "published": published,
        "paragraphs": body,
        "body": "\n\n".join(body),
    }
