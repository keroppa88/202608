"""日経の指数ページをヘッドレスブラウザで開き、画面に見えているテキストを保存する。

indexes.nikkei.co.jp は Cloudflare のボット判定が入っており、
通常のHTTP取得では 403（Just a moment...）になる。
JavaScript を実行して初めて中身が表示されるため、ブラウザで開く必要がある。

保存するのは HTML ではなく**表示テキスト**（画面を全選択してコピーしたものに相当）。
タグやクラス名に依存しないため、サイト改修で壊れにくい。

このスクリプトは**取得だけ**を行う。抽出は保存済みテキストを入力に別途実装する。

前提:
    pip install playwright
    playwright install chromium

使い方:
    python3 src/fetch_nikkei_index.py                 全ページ
    python3 src/fetch_nikkei_index.py nk225_summary   指定ページのみ
    python3 src/fetch_nikkei_index.py --show          対象一覧を表示

注意:
    Cloudflare のチャレンジは接続元IPで難易度が変わる。
    自宅回線からはほぼ通るが、データセンターIP（GitHub Actions など）からは
    弾かれることがある。まず手元で実行して通ることを確認すること。
"""

import os
import sys

from common import now_jst, report, repo_root, save_raw

# 取得対象。key はファイル名に使う。
# 日経VI は idx が未確定のため、まず index_list を取得してコードを確認する。
TARGETS = {
    "nk225_summary": (
        "日経平均 サマリー（四本値・時刻・寄与度など）",
        "https://indexes.nikkei.co.jp/nkave/archives/summary?idx=nk225",
    ),
    "nk225_profile": (
        "日経平均 プロフィル",
        "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225",
    ),
    "nkscd_profile": (
        "日経半導体株指数 プロフィル",
        "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nkscd",
    ),
    "index_list": (
        "指数一覧（カバードコール・内需50・外需50 などの大引け値）",
        "https://indexes.nikkei.co.jp/nkave/index?type=index",
    ),
}

# Cloudflare のチャレンジ画面のタイトル。これが消えるまで待つ。
CHALLENGE_TITLES = ("just a moment", "attention required", "アクセスできません")

CHALLENGE_TIMEOUT_MS = 45000
LOAD_TIMEOUT_MS = 60000
SETTLE_MS = 3000


def _looks_like_challenge(page):
    try:
        return any(t in page.title().lower() for t in CHALLENGE_TITLES)
    except Exception:
        return False


def open_and_capture(page, url):
    """ページを開き、チャレンジが解けるのを待ってから表示テキストを返す。"""
    page.goto(url, wait_until="domcontentloaded", timeout=LOAD_TIMEOUT_MS)

    if _looks_like_challenge(page):
        # チャレンジは自動で解けて元のページへ遷移する。タイトルが変わるまで待つ
        page.wait_for_function(
            "() => !/just a moment|attention required/i.test(document.title)",
            timeout=CHALLENGE_TIMEOUT_MS,
        )

    # 数値が JS で描画される場合に備えて少し落ち着かせる
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(SETTLE_MS)

    if _looks_like_challenge(page):
        raise RuntimeError("Cloudflare のチャレンジを通過できなかった")

    # HTML ではなく画面に見えているテキストを取る。
    # 表を含めて改行・タブ区切りで落ちてくるので、後段で行単位に処理できる
    text = page.inner_text("body")
    if not text.strip():
        raise RuntimeError("表示テキストが空")
    return text


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("-")]
    if "--show" in argv:
        for key, (label, url) in TARGETS.items():
            print(f"  {key:<16} {label}\n    {url}")
        return 0

    keys = args or list(TARGETS)
    unknown = [k for k in keys if k not in TARGETS]
    if unknown:
        print(f"未知の対象: {', '.join(unknown)}", file=sys.stderr)
        return 2

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "playwright が入っていない。\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    root = repo_root()
    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    ok, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 実ブラウザに近い状態にしておく。Cloudflare は UA だけでなく
        # 言語・タイムゾーン・画面サイズも見ている
        context = browser.new_context(
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()

        for key in keys:
            label, url = TARGETS[key]
            try:
                text = open_and_capture(page, url)
                # テキストは小さく、GitHub 上でそのまま読めるので圧縮しない
                path = os.path.join(raw_dir, f"nkindex_{key}.txt")
                save_raw(path, text)
                ok.append(key)
                print(
                    f"OK   {key:<16} {len(text):>7,}文字 / {text.count(chr(10)) + 1:>4}行  "
                    f"-> {os.path.relpath(path, root)}"
                )
            except Exception as e:
                errors.append((f"{label} ({key})", str(e).splitlines()[0]))
                print(f"FAIL {key:<16} {str(e).splitlines()[0][:80]}")

        context.close()
        browser.close()

    return report(ok, errors, "日経指数ページ取得")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
