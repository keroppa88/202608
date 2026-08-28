"""chart0 の financedata をこのリポジトリへコピーする。

使い方:
    python3 src/copy_finance.py chart0

chart0/financedata/{コード}.csv を data/financedata/{コード}.csv へそのまま写す。
対象は4文字の日本株コードだけ。既存ファイルは上書きし、chart0 から消えたファイルは
こちらでは削除しない。
"""

import os
import shutil
import sys

from common import repo_root


def is_stock(name):
    base = name[:-4] if name.endswith(".csv") else name
    return len(base) == 4 and base.isalnum() and not base.isalpha()


def main(argv):
    if len(argv) < 2:
        print("chart0 の場所が要る（例: python3 src/copy_finance.py chart0）", file=sys.stderr)
        return 2

    src_dir = os.path.join(argv[1], "financedata")
    if not os.path.isdir(src_dir):
        print(f"{src_dir} が無い", file=sys.stderr)
        return 2

    dst_dir = os.path.join(repo_root(), "data", "financedata")
    os.makedirs(dst_dir, exist_ok=True)

    copied = 0
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".csv") or not is_stock(name):
            continue
        shutil.copyfile(os.path.join(src_dir, name), os.path.join(dst_dir, name))
        copied += 1

    print(f"財務CSVを写した: {copied}銘柄")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
