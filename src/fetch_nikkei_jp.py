"""日経「東証大引け」記事を取得して article/japan{YYYYMM}.txt に追記する。

平日の大引け（15:00）の約50分後に掲載される。

使い方:
    python3 src/fetch_nikkei_jp.py
"""

import sys

from common import repo_root
from nikkei import collect

SEARCH_URL = (
    "https://www.nikkei.com/search"
    "?keyword=%E6%9D%B1%E8%A8%BC%E5%A4%A7%E5%BC%95%E3%81%91%E3%80%81"  # 東証大引け、
    "&volume=2"
)

MAX_CANDIDATES = 2


def matches(headline, article):
    """題名が「東証大引け」で始まる記事を対象とする。"""
    return headline.startswith("東証大引け")


def main():
    return collect(
        label="東証大引け",
        search_url=SEARCH_URL,
        raw_prefix="nikkei_jp",
        out_prefix="japan",
        matches=matches,
        max_candidates=MAX_CANDIDATES,
        root=repo_root(),
    )


if __name__ == "__main__":
    sys.exit(main())
