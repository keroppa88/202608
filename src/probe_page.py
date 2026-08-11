"""任意のページの表示テキストを見るための道具（開発用）。

新しい取得先を検討するとき、**ブラウザで開いて画面の文字を丸ごと取る**。
人がページを全選択してコピーするのと同じことをする（SPEC §2.2）。

何も書き込まない。取得だけを行う。

使い方:
    python3 src/probe_page.py <URL> [<URL> ...]
    python3 src/probe_page.py <URL> --wait <画面に出るまで待つ語>

    --wait はその語が出るまで待ってから取る。値が後から流し込まれるページ用。
"""

import sys


def _option(argv, name):
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return argv[i + 1]
    return None


def main(argv):
    from page_text import capture

    wait = _option(argv, "--wait")
    urls = [a for a in argv[1:] if a.startswith("http")]
    if not urls:
        print(__doc__)
        return 1

    for url in urls:
        print(f"\n{'=' * 70}\n{url}\n{'=' * 70}")
        try:
            text = capture(url, wait_text=wait, settle_ms=5000)
        except Exception as e:
            print(f"  取得できない: {str(e).splitlines()[0]}")
            continue
        lines = [ln for ln in text.split("\n") if ln.strip()]
        numeric = sum(1 for ln in lines if any(c.isdigit() for c in ln))
        print(f"  {len(lines)}行 / うち数字を含む行 {numeric}\n")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
