"""日経の記事を取得して月別テキストに追記する共通処理（SPEC §4A）。

検索ページと記事ページはどちらも生HTMLを保存してから抽出する。
記事の選択は「一番上」ではなく掲載日時と題名・本文の内容で判定する。
"""

import html
import json
import os
import re
import time
from datetime import datetime

from common import ExtractError, JST, fetch, now_jst, save_raw

ARTICLE_URL = "https://www.nikkei.com/article/{}/"
ARTICLE_ID_RE = re.compile(r"/article/(DGXZQ[A-Z0-9]+)")

REQUEST_INTERVAL = 0.5

RECORD_SEP = "=" * 80
BODY_SEP = "-" * 80


# --------------------------------------------------------------------------
# 抽出
# --------------------------------------------------------------------------

def article_ids(search_html):
    """検索ページの生HTMLから記事IDを出現順（新しい順）に返す。重複は除く。"""
    seen, ids = set(), []
    for m in ARTICLE_ID_RE.finditer(search_html):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def _strip_tags(fragment):
    fragment = re.sub(r"<br\s*/?>", "\n", fragment, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def _news_article(doc):
    """JSON-LD の中から NewsArticle を取り出す。"""
    for node in doc.get("@graph", [doc]) if isinstance(doc, dict) else doc:
        if isinstance(node, dict) and node.get("@type") == "NewsArticle":
            return node
    return None


def parse_article(page_html):
    """題名・掲載日時・本文を返す。構造が変わったら例外にする（黙って空を返さない）。"""
    art = None
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page_html, re.S
    ):
        try:
            art = _news_article(json.loads(m.group(1)))
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
        if art:
            break
    if not art:
        raise ExtractError("JSON-LD の NewsArticle が見つからない")

    headline = (art.get("headline") or "").strip()
    published = (art.get("datePublished") or "").strip()
    if not headline or not published:
        raise ExtractError("headline / datePublished が空")

    # 本文セクションを起点に段落を拾う。見つからなければ全体から拾う
    section = re.search(
        r'data-track-article-content="".*?(<p\s.*?)</section>', page_html, re.S
    )
    scope = section.group(1) if section else page_html

    paragraphs = []
    for m in re.finditer(r'<p class="paragraph_[^"]*">(.*?)</p>', scope, re.S):
        text = _strip_tags(m.group(1))
        if text:
            paragraphs.append(text)
    if not paragraphs:
        raise ExtractError("本文の段落が取れない")

    return {
        "headline": headline,
        "published": published,
        "paragraphs": paragraphs,
        "body": "\n\n".join(paragraphs),
    }


# --------------------------------------------------------------------------
# 出力
# --------------------------------------------------------------------------

def _fmt(dt_iso):
    return datetime.fromisoformat(dt_iso).astimezone(JST).strftime("%Y-%m-%d %H:%M:%S JST")


def target_path(root, prefix, published_iso):
    """月ファイルの振り分けは記事の掲載日基準（取得日ではない）。"""
    month = datetime.fromisoformat(published_iso).astimezone(JST).strftime("%Y%m")
    return os.path.join(root, "article", f"{prefix}{month}.txt")


def already_recorded(path, url):
    if not os.path.exists(path):
        return False
    with open(path, encoding="utf-8") as f:
        return url in f.read()


def append_record(path, article, url, fetched_at):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    record = "\n".join(
        [
            RECORD_SEP,
            f"題名      : {article['headline']}",
            f"記事年月日: {_fmt(article['published'])}",
            f"取得年月日: {fetched_at.strftime('%Y-%m-%d %H:%M:%S JST')}",
            f"URL       : {url}",
            BODY_SEP,
            article["body"],
            "",
            "",
        ]
    )
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(record)


# --------------------------------------------------------------------------

def collect(*, label, search_url, raw_prefix, out_prefix, matches, max_candidates, root):
    """記事を1本選んで追記する。戻り値は終了コード。

    matches(headline, article) -> bool で対象記事かを判定する。
    候補を上から順に見て、最初に一致したものを採用する。
    """
    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    search_html = fetch(search_url).decode("utf-8", "replace")
    save_raw(os.path.join(raw_dir, f"{raw_prefix}_search.html.gz"), search_html)

    ids = article_ids(search_html)
    if not ids:
        print(f"{label}: 検索結果に記事がない")
        return 1
    print(f"{label}: 候補 {len(ids)}件")

    selected = None
    for article_id in ids[:max_candidates]:
        url = ARTICLE_URL.format(article_id)
        page = fetch(url).decode("utf-8", "replace")
        save_raw(os.path.join(raw_dir, f"{raw_prefix}_{article_id}.html.gz"), page)

        article = parse_article(page)
        hit = matches(article["headline"], article)
        mark = "採用" if hit else "対象外"
        print(f"  [{mark}] {article['published']}  {article['headline'][:48]}")
        if hit:
            selected = (article_id, url, article)
            break
        time.sleep(REQUEST_INTERVAL)

    if not selected:
        # 該当なしを黙って正常終了させない（別の記事を拾うより失敗させる）
        print(f"{label}: 対象記事が見つからない（候補 {min(len(ids), max_candidates)}件を確認）")
        return 1

    article_id, url, article = selected
    path = target_path(root, out_prefix, article["published"])

    if already_recorded(path, url):
        # 祝日・再実行・cron の重複起動はここで吸収する。失敗ではない
        print(f"{label}: 記録済みのためスキップ（{article_id}）")
        return 0

    append_record(path, article, url, started)
    print(
        f"{label}: 追記 -> {os.path.relpath(path, root)}"
        f"（{len(article['paragraphs'])}段落 / {len(article['body'])}文字）"
    )
    return 0
