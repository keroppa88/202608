"""chart0 リポジトリの個別株を、このリポジトリへ写す。

chart0 は JST 16:40 に更新される。その後にこれを回す。

    python3 src/copy_stocks.py chart0

写すのは4桁のコードのファイルだけ。3桁は指数（TOPIX・日経平均・NYダウ…）で、
こちらには同じものが別の取り方で入っており、しかも古くまで揃っている。
並べると銘柄一覧に同じ名前が2つ出るだけなので写さない。

中身は触らない。1バイトも変えずにそのまま置く。

    data/stocks/{コード}.csv    chart0 の data/{コード}.csv をそのまま
    data/stocks/list.csv        画面に出す一覧。ここだけこちらで作る

一覧を作るのは、画面が「どのコードがあるか」を知るため。1000本のファイルを
開いて回るわけにいかないので、名前と期間と行数をここでまとめておく。
名前は chart0 の allchartlist.csv から引く。

allchartlist.csv に無いコードは一覧に載せない。上場廃止などで名前が引けなく
なったものなので、画面の選択肢には出さない。ファイル自体は消さずに置いておく。
あちらの一覧が直れば、次に写したときからまた出る。

chart0 から消えた銘柄は、こちらでは消さない。向こうの都合で消えても、
こちらに残っている値は残しておく。
"""

import csv
import os
import shutil
import sys

from common import repo_root

# 個別株のコードは4文字。数字4桁のほか、新しい形式の 130A のようなものもある
def is_stock(name):
    base = name[:-4] if name.endswith(".csv") else name
    return len(base) == 4 and base.isalnum() and not base.isalpha()


def read_names(path):
    """allchartlist.csv（見出し行なし、コード,名前）を読む。"""
    names = {}
    if not os.path.exists(path):
        return names
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if len(row) >= 2 and row[0].strip():
                names[row[0].strip()] = row[1].strip()
    return names


def span(path):
    """最初の日・最後の日・行数。日付は1列目にあり、昇順に並んでいる。"""
    first = last = ""
    rows = 0
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)                      # 見出し
        for row in reader:
            if not row or not row[0].strip():
                continue
            rows += 1
            if not first:
                first = row[0].strip()
            last = row[0].strip()
    return first, last, rows


def main(argv):
    if len(argv) < 2:
        print("chart0 の場所が要る（例: python3 src/copy_stocks.py chart0）", file=sys.stderr)
        return 2
    src_root = argv[1]
    src_dir = os.path.join(src_root, "data")
    if not os.path.isdir(src_dir):
        print(f"{src_dir} が無い", file=sys.stderr)
        return 2

    root = repo_root()
    dst_dir = os.path.join(root, "data", "stocks")
    os.makedirs(dst_dir, exist_ok=True)

    names = read_names(os.path.join(src_root, "allchartlist.csv"))
    copied = 0
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".csv") or not is_stock(name):
            continue
        shutil.copyfile(os.path.join(src_dir, name), os.path.join(dst_dir, name))
        copied += 1
    print(f"写した: {copied}銘柄")

    # 一覧は、いまこちらにあるファイルから作る。載っているものは必ず開ける
    rows = []
    skipped = []
    for name in sorted(os.listdir(dst_dir)):
        if name == "list.csv" or not name.endswith(".csv"):
            continue
        code = name[:-4]
        if code not in names:
            skipped.append(code)
            continue
        first, last, n = span(os.path.join(dst_dir, name))
        if not n:
            print(f"  {code}: 中身が無い。一覧に入れない")
            continue
        rows.append(
            {"code": code, "name": names[code], "first": first, "last": last, "rows": n}
        )

    with open(os.path.join(dst_dir, "list.csv"), "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "first", "last", "rows"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"一覧: {len(rows)}銘柄")
    if skipped:
        print(f"  allchartlist.csv に無いので一覧から外した: {' '.join(skipped[:20])}"
              + (f" ほか{len(skipped) - 20}" if len(skipped) > 20 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
