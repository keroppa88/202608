"""ウェブページを開いて「画面に見えている文字」を丸ごと取る（SPEC §2.2）。

人が画面を全選択してコピーしたものと同じテキストを得る。それだけを行う。

    capture(url)        ブラウザで開いて表示テキストを丸ごと取る
    browser_session()   同じブラウザで複数ページを続けて読む

**HTML は読まない。抜かない。** タグ・クラス名・属性・リンク先・<title>、
どれも見ない。HTML はサイト側が対策を打ってくる場所で、見た目が同じ日でも
内部構造が変わる。そこに付き合うと壊れ続ける。画面に出ている文字は変わらない。

**取得の段階で判断しない。** 特定の語や形が出るのを待つことはしない。
描画を待って丸ごと取り、そのまま返す。ボット判定の画面でもエラー画面でも、
出ているものをそのまま返す。呼び出し側はそれを丸ごと保存する。
取れたかどうかは、保存したテキストから抽出した件数で後から判断する。
"""

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _screen(page, settle_ms):
    """今ブラウザに出ている文字を丸ごと返す。範囲の絞り込みはしない。"""
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        # 広告や配信が鳴り止まないページもある。待てなくても画面は取る
        pass
    page.wait_for_timeout(settle_ms)
    return page.inner_text("body")


class Reader:
    """開いているブラウザ1枚。読むか、画面の文字をクリックするか、だけ。"""

    def __init__(self, page, timeout_ms, settle_ms):
        self._page = page
        self._timeout_ms = timeout_ms
        self._settle_ms = settle_ms

    def __call__(self, url):
        """URL を開いて、画面の文字を丸ごと返す。"""
        self._page.goto(url, wait_until="domcontentloaded", timeout=self._timeout_ms)
        return _screen(self._page, self._settle_ms)

    def click(self, text):
        """画面に出ている文字をクリックして、移った先の画面を丸ごと返す。

        人が画面を見て、その文字をクリックするのと同じ。手掛かりは画面の文字だけで、
        リンクの書かれ方（タグ・クラス名・href）は見ない。

        戻り値は (表示テキスト, 移った先のURL)。URL はブラウザのアドレス欄に
        出ているもので、HTML から抜いたものではない。
        """
        self._page.get_by_text(text, exact=False).first.click(timeout=self._timeout_ms)
        try:
            self._page.wait_for_load_state("domcontentloaded", timeout=self._timeout_ms)
        except Exception:
            pass
        return _screen(self._page, self._settle_ms), self._page.url


def browser_session(*, timeout_ms=60000, settle_ms=10000):
    """ブラウザを1回だけ立ち上げ、複数ページを続けて読むための文脈を返す。

    settle_ms … 描画を待つ時間。特定の語や形を待ち合わせることはしない

    使い方:
        with browser_session() as read:
            text = read(url)                   # 開いて全部コピー
            text, url = read.click("見出し")    # 画面の文字をクリックして移る

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
                yield Reader(page, timeout_ms, settle_ms)
            finally:
                context.close()
                browser.close()

    return session()


def capture(url, **kw):
    """ブラウザでページを開き、画面に出ている文字を丸ごと返す。"""
    with browser_session(**kw) as read:
        return read(url)
