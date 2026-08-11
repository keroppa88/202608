"""任意のページの表示テキストを見るための道具（開発用）。

新しい取得先を検討するとき、**ブラウザで開いて画面の文字を丸ごと取る**。
人がページを全選択してコピーするのと同じことをする（CLAUDE.md）。

何も書き込まない。取得だけを行う。取れた文字は全部そのまま出す。

使い方:
    python3 src/probe_page.py <URL> [<URL> ...] [--settle 秒]
"""

import sys


def main(argv):
    from page_text import browser_session

    args = argv[1:]
    settle_s = 10
    if "--settle" in args:
        i = args.index("--settle")
        settle_s = int(args[i + 1])
        args = args[:i] + args[i + 2 :]

    urls = [a for a in args if a.startswith("http")]
    if not urls:
        print(__doc__)
        return 1

    with browser_session(settle_ms=settle_s * 1000) as read:
        for url in urls:
            print(f"\n{'=' * 70}\n{url}（{settle_s}秒待つ）\n{'=' * 70}")
            try:
                text = read(url)
            except Exception as e:
                print(f"  開けない: {str(e).splitlines()[0]}")
                continue
            lines = [ln for ln in text.split("\n") if ln.strip()]
            numeric = sum(1 for ln in lines if any(c.isdigit() for c in ln))
            print(f"  {len(lines)}行 / うち数字を含む行 {numeric}\n")
            print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
