"""日経「米国株」の大引け記事を取得して article/us{YYYYMM}.txt に追記する。

米国市場の引け（16:00 ET）の後、JST の早朝 5時台に掲載される。

この検索は1米国営業日につき3本ヒットする（寄り付き / 引け速報 / 大引け）。
実行時刻によっては最新が寄り付き記事になるため、位置ではなく内容で判定する。

    寄り付き   … 題名に「始まる」。本文に「終値」がない
    引け速報   … 題名に値幅が入らない
    大引け     … 題名に「◯◯ドル高 / ◯◯ドル安」。本文に「終値」がある  ← これを採る

使い方:
    python3 src/fetch_nikkei_us.py
"""

import re
import sys

from common import repo_root
from nikkei import collect

SEARCH_URL = (
    "https://www.nikkei.com/search"
    "?keyword=%E7%B1%B3%E5%9B%BD%E6%A0%AA%E3%80%81%E3%80%80NQN"        # 米国株、　NQN
    "%E3%83%8B%E3%83%A5%E3%83%BC%E3%83%A8%E3%83%BC%E3%82%AF%E3%80%80"  # ニューヨーク
    "%E7%B1%B3%E6%A0%AA%E5%BC%8F%E5%B8%82%E5%A0%B4%E3%81%A7"           # 米株式市場で
    "%E3%83%80%E3%82%A6%E5%B7%A5%E6%A5%AD%E6%A0%AA30"                  # ダウ工業株30
    "%E7%A8%AE%E5%B9%B3%E5%9D%87%E3%81%AF"                             # 種平均は
    "&volume=10"
)

# 1営業日あたり3本なので、10件見れば直近3営業日分をカバーできる
MAX_CANDIDATES = 10

# 大引け記事の題名に必ず入る値幅。例: 「ダウ反発し151ドル高」「ダウ反落し464ドル安」
CLOSING_HEADLINE = re.compile(r"\d+\s*ドル[高安]")


def matches(headline, article):
    """大引け記事だけを対象とする。題名と本文の両方で確認する。"""
    if not CLOSING_HEADLINE.search(headline):
        return False
    # 寄り付き記事を取り違えないための二重確認
    return "終値" in article["body"]


def main():
    return collect(
        label="米国株・大引け",
        search_url=SEARCH_URL,
        raw_prefix="nikkei_us",
        out_prefix="us",
        matches=matches,
        max_candidates=MAX_CANDIDATES,
        root=repo_root(),
    )


if __name__ == "__main__":
    sys.exit(main())
