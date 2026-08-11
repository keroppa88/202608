"""松井証券の「投資指標(松井証券店内)」を取得して追記する（SPEC §4G）。

https://www.matsui.co.jp/market/stock/netstock-info/

取引動向・市場別株式売買代金・信用残・評価損益率など、松井証券店内の数値。
ログインなしで見えるのは**前営業日更新分**なので、ページ冒頭に出る日付
（例「8/7(金)」）の数値として記録する。

数値は静的HTMLに入っていない（別システムから配信され、素のHTMLには
「情報が正しく表示できません」と出る）。**ヘッドレスブラウザで開く**。
表示テキストに直してから抽出する（SPEC §2.2）。

    data/raw/YYYY-MM-DD/matsui.txt   表示テキスト
    data/matsui.csv                  指標

使い方:
    python3 src/fetch_matsui.py
    python3 src/fetch_matsui.py --dump   取れた表示テキストを出すだけ（書き込まない）
"""

import os
import sys

from common import now_jst, repo_root, save_raw
from page_text import capture

URL = "https://www.matsui.co.jp/market/stock/netstock-info/"

# 数値は配信元から後から差し込まれる。描画を待つ
SETTLE_MS = 8000


def main(argv):
    root = repo_root()
    started = now_jst()

    text = capture(URL, settle_ms=SETTLE_MS)
    save_raw(
        os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"), "matsui.txt"),
        text,
    )

    if "--dump" in argv:
        print(text)
        return 0

    print("抽出は未実装")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
