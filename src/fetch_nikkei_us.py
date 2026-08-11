"""日経「米国株」の大引け記事を取得して article/us{YYYYMM}.txt に追記する。

米国市場の引け（16:00 ET）の後、JST の早朝 5時台に掲載される。

1米国営業日につき3本出る（寄り付き / 引け速報 / 大引け）。
実行時刻によっては最新が寄り付き記事になるため、位置ではなく内容で判定する。

    寄り付き   … 題名に「始まる」。本文に「終値」がない
    引け速報   … 題名に値幅が入らない
    大引け     … 題名に「◯◯ドル高 / ◯◯ドル安」。本文に「終値」がある  ← これを採る

一覧ページを開いて画面の文字を丸ごと保存し、その画面に出ている見出しを
クリックして記事へ移る（CLAUDE.md）。

使い方:
    python3 src/fetch_nikkei_us.py
"""

import re
import sys

from common import repo_root
from nikkei import collect

# 見出しが画面に出るページ。上から順に見る
LIST_URLS = [
    "https://www.nikkei.com/markets/worldidx/",
    "https://www.nikkei.com/markets/",
    "https://www.nikkei.com/search?keyword=%E7%B1%B3%E5%9B%BD%E6%A0%AA%E3%80%81&volume=10",
]

MAX_CANDIDATES = 25

# 大引け記事の題名に必ず入る値幅。例: 「ダウ反発し151ドル高」「ダウ反落し464ドル安」
CLOSING_HEADLINE = re.compile(r"\d+\s*ドル[高安]")


def looks_like(line):
    """一覧の画面に出ている行が米国株の大引け見出しに見えるか。"""
    return bool(CLOSING_HEADLINE.search(line)) and ("米国株" in line or "ダウ" in line)


def matches(headline, article):
    """記事を開いた上での最終判定。題名と本文の両方で確認する。"""
    if not CLOSING_HEADLINE.search(headline):
        return False
    # 寄り付き記事を取り違えないための二重確認
    return "終値" in article["body"]


def main():
    return collect(
        label="米国株・大引け",
        list_urls=LIST_URLS,
        raw_prefix="nikkei_us",
        out_prefix="us",
        looks_like=looks_like,
        matches=matches,
        max_candidates=MAX_CANDIDATES,
        root=repo_root(),
    )


if __name__ == "__main__":
    sys.exit(main())
