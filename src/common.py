"""共通処理。標準ライブラリのみを使う。

取得（fetch）と保存（save_raw）だけを担当し、抽出は各スクリプト側に置く。
生データは無加工で保存する（SPEC §2.1）。
"""

import gzip
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class FetchError(Exception):
    """取得そのものが失敗した（HTTP・ネットワーク）。"""


class ExtractError(Exception):
    """取得はできたが、中身が期待と違う。"""


def now_jst():
    return datetime.now(JST)


def fetch(url, *, retries=3, timeout=30, headers=None):
    """生バイト列を返す。失敗時は指数バックオフで再試行する。"""
    h = {"User-Agent": UA, "Accept-Language": "ja,en;q=0.8"}
    if headers:
        h.update(headers)

    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.read()
        except Exception as e:  # HTTPError / URLError / socket.timeout
            last = e
            if attempt < retries:
                time.sleep(2**attempt)
    raise FetchError(f"{url} -> {last}")


def save_raw(path, data):
    """生データをそのまま書き出す。中身には一切手を加えない。

    .gz で終わるパスは gzip 圧縮して保存する。可逆なので生データ保存の方針は
    変わらない。無圧縮だと検索ページだけで 1日 2MB になるため既定は圧縮。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blob = data.encode("utf-8") if isinstance(data, str) else data
    if path.endswith(".gz"):
        with gzip.open(path, "wb", compresslevel=9) as f:
            f.write(blob)
    else:
        with open(path, "wb") as f:
            f.write(blob)
    return path


def load_raw(path):
    """save_raw で保存した生データを読み戻す。再抽出はこれを入力にする。"""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as f:
        return f.read()


def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def report(ok, errors, label):
    """結果を標準出力に出し、エラーがあれば終了コード1を返す。"""
    print(f"\n=== {label} ===")
    print(f"成功: {len(ok)}件")
    if errors:
        print(f"失敗: {len(errors)}件")
        for name, msg in errors:
            print(f"  - {name}: {msg}")
        return 1
    return 0
