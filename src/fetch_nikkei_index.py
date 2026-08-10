"""日経の指数ページを開き、画面に見えているテキストを丸ごと保存する（SPEC §4C）。

indexes.nikkei.co.jp は Cloudflare のボット判定が入っており、
通常のHTTP取得では 403（Just a moment...）になる。
JavaScript を実行して初めて中身が表示されるため、ブラウザで開く必要がある。

このスクリプトは**取得だけ**を行う。抽出は保存済みテキストを入力に別途実装する。

前提:
    pip install playwright
    playwright install chromium

使い方:
    python3 src/fetch_nikkei_index.py                 全ページ
    python3 src/fetch_nikkei_index.py nk225_summary   指定ページのみ
    python3 src/fetch_nikkei_index.py --show          対象一覧を表示

注意:
    Cloudflare のチャレンジは接続元IPで難易度が変わる。
    自宅回線からはほぼ通るが、データセンターIP（GitHub Actions など）からは
    弾かれることがある。通るかどうかはまだ確認できていない。
"""

import os
import sys

from common import now_jst, report, repo_root, save_raw
from page_text import browser_session

# 取得対象。key はファイル名に使う。
# 日経VI は idx が未確定のため、まず index_list を取得してコードを確認する。
TARGETS = {
    "nk225_summary": (
        "日経平均 サマリー（四本値・時刻・寄与度など）",
        "https://indexes.nikkei.co.jp/nkave/archives/summary?idx=nk225",
    ),
    "nk225_profile": (
        "日経平均 プロフィル",
        "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225",
    ),
    "nkscd_profile": (
        "日経半導体株指数 プロフィル",
        "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nkscd",
    ),
    "index_list": (
        "指数一覧（カバードコール・内需50・外需50 などの大引け値）",
        "https://indexes.nikkei.co.jp/nkave/index?type=index",
    ),
}


def main(argv):
    if "--show" in argv:
        for key, (label, url) in TARGETS.items():
            print(f"  {key:<16} {label}\n    {url}")
        return 0

    keys = [a for a in argv[1:] if not a.startswith("-")] or list(TARGETS)
    unknown = [k for k in keys if k not in TARGETS]
    if unknown:
        print(f"未知の対象: {', '.join(unknown)}", file=sys.stderr)
        return 2

    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            "playwright が入っていない。\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 2

    root = repo_root()
    raw_dir = os.path.join(root, "data", "raw", now_jst().strftime("%Y-%m-%d"))

    ok, errors = [], []
    with browser_session() as read:
        for key in keys:
            label, url = TARGETS[key]
            try:
                text = read(url)
                # テキストは小さく、GitHub 上でそのまま読めるので圧縮しない
                path = os.path.join(raw_dir, f"nkindex_{key}.txt")
                save_raw(path, text)
                ok.append(key)
                print(
                    f"OK   {key:<16} {len(text):>7,}文字 / "
                    f"{text.count(chr(10)) + 1:>4}行  -> {os.path.relpath(path, root)}"
                )
            except Exception as e:
                reason = str(e).splitlines()[0]
                errors.append((f"{label} ({key})", reason))
                print(f"FAIL {key:<16} {reason[:80]}")

    return report(ok, errors, "日経指数ページ取得")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
