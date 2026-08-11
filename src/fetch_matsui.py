"""松井証券の「投資指標(松井証券店内)」を取得して追記する（SPEC §4G）。

https://www.matsui.co.jp/market/stock/netstock-info/

取引動向・市場別株式売買代金・信用残・評価損益率など、松井証券店内の数値。
ログインなしで見えるのは**前営業日更新分**なので、ページ冒頭に出る日付
（例「8/7(金)」）の数値として記録する。

数値は静的HTMLに入っていない。素のHTMLでは表の場所が空で、代わりに
「情報が正しく表示できません」と出る。中身は Rtoaster（js.rtoaster.jp）が
後から流し込む。**ヘッドレスブラウザで開き、流し込まれるまで待つ**。
表示テキストに直してから抽出する（SPEC §2.2）。

    data/raw/YYYY-MM-DD/matsui.txt   表示テキスト
    data/matsui.csv                  指標

使い方:
    python3 src/fetch_matsui.py
    python3 src/fetch_matsui.py --probe   出方を調べる（何も書き込まない）
"""

import os
import sys

from common import now_jst, repo_root, save_raw
from page_text import UA

URL = "https://www.matsui.co.jp/market/stock/netstock-info/"

# 数値が入った証拠になる語。これが出るまで待つ
MARKER = "取引動向"

# 表が空のときに出る文言
FALLBACK = "情報が正しく表示できません"

WAIT_MS = 40000


def read(*, channel=None, log=None):
    """ページを開き、表が埋まるまで待って表示テキストを返す。"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        kw = {"headless": True}
        if channel:
            kw["channel"] = channel
        browser = p.chromium.launch(**kw)
        context = browser.new_context(
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            user_agent=UA,
        )
        page = context.new_page()
        if log is not None:
            page.on(
                "response",
                lambda r: log.append((r.status, r.url))
                if "rtoaster" in r.url
                else None,
            )
            page.on(
                "requestfailed",
                lambda r: log.append(("失敗 " + (r.failure or "?"), r.url))
                if "rtoaster" in r.url
                else None,
            )
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            try:
                page.wait_for_function(
                    "m => document.body.innerText.includes(m)",
                    arg=MARKER,
                    timeout=WAIT_MS,
                )
            except Exception:
                pass  # 出なくても、そのときの見た目を持ち帰って調べる
            return page.inner_text("body")
        finally:
            context.close()
            browser.close()


def probe():
    """ヘッドレスシェルと通常のChromiumで出方を比べる。"""
    for channel in (None, "chromium"):
        log = []
        label = channel or "headless shell"
        try:
            text = read(channel=channel, log=log)
        except Exception as e:
            print(f"[{label}] 起動できない: {str(e).splitlines()[0]}")
            continue

        print(f"\n===== {label} =====")
        print(f"  {MARKER} が出た: {MARKER in text}")
        print(f"  代替文が残っている: {FALLBACK in text}")
        print(f"  rtoaster への通信 {len(log)}件")
        for status, url in log[:20]:
            print(f"    {status}  {url[:140]}")
        if MARKER in text:
            print("----- 表示テキスト -----")
            print(text)
            return 0
    return 1


def main(argv):
    root = repo_root()
    started = now_jst()

    if "--probe" in argv:
        return probe()

    text = read()
    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), "matsui.txt"),
        text,
    )
    print("抽出は未実装")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
