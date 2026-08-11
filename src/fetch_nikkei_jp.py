"""日経「東証大引け」記事を取得して article/japan{YYYYMM}.txt に追記する。

平日の大引け（15:00）の約50分後に掲載される。

一覧ページを開いて画面の文字を丸ごと保存し、その画面に出ている見出しを
クリックして記事へ移る（CLAUDE.md）。

使い方:
    python3 src/fetch_nikkei_jp.py
"""

import sys

from common import repo_root
from nikkei import collect

# 見出しが画面に出るページ。上から順に見る
LIST_URLS = [
    "https://www.nikkei.com/markets/kabu/",
    "https://www.nikkei.com/markets/",
    "https://www.nikkei.com/search?keyword=%E6%9D%B1%E8%A8%BC%E5%A4%A7%E5%BC%95%E3%81%91&volume=2",
]

MAX_CANDIDATES = 25


def looks_like(line):
    """一覧の画面に出ている行が「東証大引け」の見出しに見えるか。"""
    return line.startswith("東証大引け")


def matches(headline, article):
    """記事を開いた上での最終判定。"""
    return headline.startswith("東証大引け")


def main():
    return collect(
        label="東証大引け",
        list_urls=LIST_URLS,
        raw_prefix="nikkei_jp",
        out_prefix="japan",
        looks_like=looks_like,
        matches=matches,
        max_candidates=MAX_CANDIDATES,
        root=repo_root(),
    )


if __name__ == "__main__":
    sys.exit(main())
