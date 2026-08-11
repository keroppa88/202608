"""任意のページの表示テキストを見るための道具（開発用）。

新しい取得先を検討するとき、そのページの数値が静的HTMLに入っているのか、
JavaScript で後から流し込まれるのかを確かめる必要がある。
中身を見ないと抽出は書けないので、まず表示テキストをそのまま出す。

何も書き込まない。取得だけを行う。

使い方:
    python3 src/probe_page.py <URL> [<URL> ...] [--wait <画面に出るまで待つ語>]

    --wait を付けるとヘッドレスブラウザで開き、その語が出るまで待つ。
    付けなければ静的HTMLとブラウザの両方で取って、違いを並べて出す。
"""

import sys


def _option(argv, name):
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return argv[i + 1]
    return None


def static_text(url):
    from common import fetch
    from page_text import text_from_html

    return text_from_html(fetch(url).decode("utf-8", "replace"))


def browser_text(url, wait_text=None):
    from page_text import capture

    return capture(url, wait_text=wait_text, settle_ms=5000)


def show(label, url, getter):
    print(f"\n{'=' * 70}\n[{label}] {url}\n{'=' * 70}")
    try:
        text = getter()
    except Exception as e:
        print(f"  取得できない: {str(e).splitlines()[0]}")
        return
    lines = [ln for ln in text.split("\n") if ln.strip()]
    numeric = sum(1 for ln in lines if any(c.isdigit() for c in ln))
    print(f"  {len(lines)}行 / うち数字を含む行 {numeric}\n")
    print(text)


def main(argv):
    wait = _option(argv, "--wait")
    urls = [a for a in argv[1:] if a.startswith("http")]
    if not urls:
        print(__doc__)
        return 1

    for url in urls:
        if wait:
            show("ブラウザ", url, lambda u=url: browser_text(u, wait))
        else:
            show("静的HTML", url, lambda u=url: static_text(u))
            show("ブラウザ", url, lambda u=url: browser_text(u))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
