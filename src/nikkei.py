"""日経の記事を取得して月別テキストに追記する共通処理（SPEC §4A / §4B）。

ページは「画面に見えている文字」として丸ごと保存し、抽出はそのテキストだけを
入力に行う。タグ・クラス名・属性は一切見ない（SPEC §2.2）。

記事の選択は「一番上」ではなく、掲載日時と題名・本文の内容で判定する。
"""

import os
import re
import time

import nikkei_text
from common import ExtractError, fetch, now_jst, save_raw
from page_text import text_from_html

ARTICLE_URL = "https://www.nikkei.com/article/{}/"
ARTICLE_ID_RE = re.compile(r"/article/(DGXZQ[A-Z0-9]+)")

REQUEST_INTERVAL = 0.5

RECORD_SEP = "=" * 80
BODY_SEP = "-" * 80


def article_ids(search_html):
    """検索ページから記事IDを出現順（新しい順）に返す。重複は除く。

    リンク先は画面に表示されない情報なので、ここだけは HTML から拾う。
    人がリンクをクリックするのに相当する部分で、記事の中身の解釈ではない。
    """
    seen, ids = set(), []
    for m in ARTICLE_ID_RE.finditer(search_html):
        if m.group(1) not in seen:
            seen.add(m.group(1))
            ids.append(m.group(1))
    return ids


def target_path(root, prefix, published):
    """月ファイルの振り分けは記事の掲載日基準（取得日ではない）。"""
    return os.path.join(root, "article", f"{prefix}{published:%Y%m}.txt")


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
            f"記事年月日: {article['published']:%Y-%m-%d %H:%M:%S JST}",
            f"取得年月日: {fetched_at:%Y-%m-%d %H:%M:%S JST}",
            f"URL       : {url}",
            BODY_SEP,
            article["body"],
            "",
            "",
        ]
    )
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(record)


def collect(*, label, search_url, raw_prefix, out_prefix, matches, max_candidates, root):
    """記事を1本選んで追記する。戻り値は終了コード。

    matches(headline, article) -> bool で対象記事かを判定する。
    候補を上から順に見て、最初に一致したものを採用する。
    """
    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    search_html = fetch(search_url).decode("utf-8", "replace")
    save_raw(
        os.path.join(raw_dir, f"{raw_prefix}_search.txt"), text_from_html(search_html)
    )

    ids = article_ids(search_html)
    if not ids:
        print(f"{label}: 検索結果に記事がない")
        return 1
    print(f"{label}: 候補 {len(ids)}件")

    selected = None
    for article_id in ids[:max_candidates]:
        url = ARTICLE_URL.format(article_id)
        page = fetch(url).decode("utf-8", "replace")

        # 見たままのテキストを丸ごと保存してから、そのテキストだけで抽出する
        text = text_from_html(page)
        save_raw(os.path.join(raw_dir, f"{raw_prefix}_{article_id}.txt"), text)

        try:
            article = nikkei_text.parse(text)
        except nikkei_text.ExtractError as e:
            raise ExtractError(f"{article_id}: {e}") from e

        hit = matches(article["headline"], article)
        print(
            f"  [{'採用' if hit else '対象外'}] "
            f"{article['published']:%Y-%m-%d %H:%M}  {article['headline'][:46]}"
        )
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
