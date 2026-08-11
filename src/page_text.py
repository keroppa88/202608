"""ウェブページから「画面に見えている文字」を丸ごと取る（SPEC §2.2）。

人が画面を全選択してコピーしたものと同じテキストを得る。
HTML のタグ・クラス名・属性は一切見ないため、サイト改修の影響を受けない。

取得手段は2つ。

    capture(url)        ヘッドレスブラウザで開いて表示テキストを取る。
                        JavaScript 描画やボット判定のあるページはこちら。
    text_from_html(s)   取得済みHTMLを表示テキストに変換する。
                        中身が静的HTMLに入っているページ用。ブラウザが要らない。

どちらも戻り値は同じ「見たままのテキスト」なので、抽出側は区別しなくてよい。
"""

import html as _html
import re

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# ブラウザで表示されない要素。テキスト化の前に落とす
_INVISIBLE = re.compile(
    r"(?is)<(script|style|noscript|template|head)[^>]*>.*?</\1>"
)
# 改行として扱うタグの終わり
_BREAKS = re.compile(r"(?is)<br\s*/?>|</(p|div|li|tr|h[1-6]|section|article|td|th)>")

CHALLENGE = re.compile(r"just a moment|attention required|アクセスできません", re.I)


def text_from_html(source):
    """HTML を「見たままのテキスト」に変換する。"""
    t = _INVISIBLE.sub(" ", source)
    t = _BREAKS.sub("\n", t)
    t = _html.unescape(re.sub(r"<[^>]+>", " ", t))
    lines = [re.sub(r"[ \t　]+", " ", ln).strip() for ln in t.split("\n")]
    return "\n".join(ln for ln in lines if ln)


def _read_page(page, url, timeout_ms, settle_ms, challenge_ms, wait_text=None, wait_regex=None):
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

    if CHALLENGE.search(page.title() or ""):
        # ボット判定の画面は自動で解けて元ページへ遷移する。消えるまで待つ
        page.wait_for_function(
            "() => !/just a moment|attention required/i.test(document.title)",
            timeout=challenge_ms,
        )

    if wait_text:
        # 中身が後から流し込まれるページ。決め打ちの秒数で待つと、
        # 遅れた日は空のまま持ち帰ってしまう。語が出るまで待つ
        page.wait_for_function(
            "m => document.body.innerText.includes(m)",
            arg=wait_text,
            timeout=challenge_ms,
        )

    if wait_regex:
        # 項目名は最初から出ていて値だけが後から入るページがある。
        # 語の有無では待てないので「項目名のすぐ後ろに数字」を条件にする
        page.wait_for_function(
            "m => new RegExp(m).test(document.body.innerText)",
            arg=wait_regex,
            timeout=challenge_ms,
        )

    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(settle_ms)

    if CHALLENGE.search(page.title() or ""):
        raise RuntimeError("ボット判定を通過できなかった")

    # 画面に見えている文字を全部。範囲の絞り込みはしない
    text = page.inner_text("body")
    if not text.strip():
        raise RuntimeError("表示テキストが空")
    return text


def browser_session(*, timeout_ms=60000, settle_ms=3000, challenge_ms=45000, wait_text=None, wait_regex=None):
    """ブラウザを1回だけ立ち上げ、複数ページを続けて読むための文脈を返す。

    wait_text  … その語が画面に出るまで待つ。中身が後から流し込まれるページ用
    wait_regex … 正規表現で待つ。項目名は最初から出ていて値だけ後から入るページ用

    使い方:
        with browser_session() as read:
            text = read(url)

    playwright が必要:
        pip install playwright && playwright install chromium
    """
    from contextlib import contextmanager

    from playwright.sync_api import sync_playwright

    @contextmanager
    def session():
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # 実ブラウザに近い状態にする。言語・タイムゾーン・画面サイズも見られている
            context = browser.new_context(
                locale="ja-JP",
                timezone_id="Asia/Tokyo",
                viewport={"width": 1280, "height": 900},
                user_agent=UA,
            )
            page = context.new_page()
            try:
                yield lambda url: _read_page(
                    page, url, timeout_ms, settle_ms, challenge_ms, wait_text, wait_regex
                )
            finally:
                context.close()
                browser.close()

    return session()


def capture(url, **kw):
    """ヘッドレスブラウザでページを開き、表示テキストを丸ごと返す。"""
    with browser_session(**kw) as read:
        return read(url)
