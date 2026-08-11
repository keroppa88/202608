"""日経の記事を取得して月別テキストに追記する共通処理（SPEC §4A / §4B）。

一覧ページを開いて画面の文字を丸ごと保存する。その画面に出ている見出しの中から
対象を選び、**その文字をクリック**して記事へ移る。移った先も丸ごと保存し、
抽出は保存したテキストだけを入力に行う。

HTML は読まない。リンク先も抜かない（CLAUDE.md）。記事の URL はブラウザの
アドレス欄に出ているものを使う。
"""

import os

import nikkei_text
from common import ExtractError, now_jst, save_raw

RECORD_SEP = "=" * 80
BODY_SEP = "-" * 80

# 見出し行の末尾に付く掲載時刻。例:「東証大引け ○○ （8/10 15:52）」
TIME_SUFFIX = "（"


def headline_candidates(text, is_target):
    """画面の文字から、対象になりそうな見出し行を出現順に返す。重複は除く。"""
    seen, out = set(), []
    for line in text.split("\n"):
        line = line.strip()
        if not line or line in seen:
            continue
        if is_target(line):
            seen.add(line)
            out.append(line)
    return out


def clickable(line):
    """クリックの手掛かりにする文字。掲載時刻の括弧は画面上で別要素のことがある。"""
    head = line.split(TIME_SUFFIX)[0].strip()
    return head or line


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


def collect(*, label, list_urls, raw_prefix, out_prefix, looks_like, matches, max_candidates, root):
    """記事を1本選んで追記する。戻り値は終了コード。

    list_urls   … 見出しが画面に出る一覧ページ。上から順に見る
    looks_like(line) -> bool   画面の1行が対象の見出しに見えるか
    matches(headline, article) -> bool   記事を開いた上での最終判定
    """
    from page_text import browser_session

    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    selected = None
    seen_urls = set()
    tried = 0

    with browser_session() as read:
        for list_url in list_urls:
            if selected:
                break
            slug = list_url.rstrip("/").rsplit("/", 1)[-1] or "list"

            # 一覧ページも丸ごと保存する。見出しが出ていなければ、この全文が理由になる
            list_text = read(list_url)
            save_raw(os.path.join(raw_dir, f"{raw_prefix}_{slug}.txt"), list_text)

            heads = headline_candidates(list_text, looks_like)
            print(f"{label}: {list_url} → 候補 {len(heads)}件")

            for line in heads[:max_candidates]:
                if tried >= max_candidates:
                    break
                tried += 1
                try:
                    text, url = read.click(clickable(line))
                except Exception as e:
                    print(f"  [開けない] {line[:46]} … {str(e).splitlines()[0]}")
                    read(list_url)
                    continue

                if url in seen_urls:
                    read(list_url)
                    continue
                seen_urls.add(url)

                name = url.rstrip("/").rsplit("/", 1)[-1][:60] or f"n{tried}"
                save_raw(os.path.join(raw_dir, f"{raw_prefix}_{name}.txt"), text)

                try:
                    article = nikkei_text.parse(text)
                except nikkei_text.ExtractError as e:
                    raise ExtractError(f"{url}: {e}") from e

                hit = matches(article["headline"], article)
                print(
                    f"  [{'採用' if hit else '対象外'}] "
                    f"{article['published']:%Y-%m-%d %H:%M}  {article['headline'][:46]}"
                )
                if hit:
                    selected = (url, article)
                    break
                # 一覧に戻って次の見出しを見る
                read(list_url)

    if not selected:
        # 該当なしを黙って正常終了させない（別の記事を拾うより失敗させる）
        print(f"{label}: 対象記事が見つからない（{tried}件を確認）")
        return 1

    url, article = selected
    path = target_path(root, out_prefix, article["published"])

    if already_recorded(path, url):
        # 祝日・再実行・cron の重複起動はここで吸収する。失敗ではない
        print(f"{label}: 記録済みのためスキップ")
        return 0

    append_record(path, article, url, started)
    print(
        f"{label}: 追記 -> {os.path.relpath(path, root)}"
        f"（{len(article['paragraphs'])}段落 / {len(article['body'])}文字）"
    )
    return 0
