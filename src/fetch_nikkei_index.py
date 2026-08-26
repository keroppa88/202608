"""日経の指数ページを開き、画面に見えているテキストを丸ごと保存する（SPEC §4C）。

indexes.nikkei.co.jp は Cloudflare のボット判定が入っており、
通常のHTTP取得では 403（Just a moment...）になる。
JavaScript を実行して初めて中身が表示されるため、ブラウザで開く必要がある。

取得した表示テキストは `data/raw/` に残し、そこから抽出して3つのCSVに追記する。

    data/nikkei_ohlc.csv        四本値（大引け値のみの指数は終値だけ入る）
    data/nikkei_ohlc_time.csv   四本値がついた時刻
    data/nikkei225_detail.csv   日経平均の詳細（除数・PER・PBR・寄与度など）

前提:
    pip install playwright
    playwright install chromium

使い方:
    python3 src/fetch_nikkei_index.py                 全ページ
    python3 src/fetch_nikkei_index.py nk225_summary   指定ページのみ
    python3 src/fetch_nikkei_index.py --show          対象一覧を表示

注意:
    Cloudflare のチャレンジは接続元IPで難易度が変わる。
    日経平均サマリーのPER等が動的取得前の「-」なら待って再取得する。
    最終的に一部ページの抽出に失敗しても、他ページから取れた指数は保存する。
"""

import csv
import os
import sys
import time

import nikkei_index_text as N
from common import now_jst, report, repo_root, save_raw
from page_text import browser_session

# 取得対象。key はファイル名に使う。
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
    "nk225vi_profile": (
        "日経VI（日経平均ボラティリティー・インデックス） プロフィル",
        "https://indexes.nikkei.co.jp/nkave/index/profile?idx=nk225vi",
    ),
    "index_list": (
        "指数一覧（カバードコール・内需50・外需50 などの大引け値）",
        "https://indexes.nikkei.co.jp/nkave/index?type=index",
    ),
}


# 一覧から拾う指数（大引け値のみ）
LIST_TARGETS = [
    "日経平均カバードコール・インデックス",
    "日経平均カバードコールATMインデックス",
    "日経平均内需株50指数",
    "日経平均外需株50指数",
]

# ページの表記をこちらの呼び名に直す。保存も画面もこの名前で通す
RENAME = {
    "日経平均ボラティリティー・インデックス": "日経VI",
    "日経平均内需株50指数": "日経内需株50",
    "日経平均外需株50指数": "日経外需株50",
    "日経平均カバードコール・インデックス": "日経カバードコール",
    "日経平均カバードコールATMインデックス": "日経カバードコールATM",
}

SUMMARY_RETRIES = 3
SUMMARY_RETRY_WAIT = 5
SUMMARY_PLACEHOLDERS = ("-%", "-倍", "- 兆円", "- 億円")


def our_name(name):
    return RENAME.get(name, name)


def _summary_details_incomplete(text):
    """PER等の動的データ部分に「-」が残っているかを見る。"""
    start = text.find("配当利回り")
    end = text.find("通貨建て日経平均", start + 1)
    if start < 0 or end < 0:
        return True
    block = text[start:end]
    return any(token in block for token in SUMMARY_PLACEHOLDERS)


OHLC_HEADER = ["trade_date", "name", "open", "high", "low", "close", "fetched_at"]
TIME_HEADER = ["trade_date", "name", "open_time", "high_time", "low_time", "fetched_at"]
DETAIL_HEADER = ["trade_date", "group", "key", "sub", "value", "unit", "fetched_at"]


def _merge(path, header, keys, rows):
    """キーが同じ行は上書きし、並べ直して書き戻す。再実行しても二重にならない。"""
    existing = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                existing[tuple(r[k] for k in keys)] = r
    for r in rows:
        existing[tuple(str(r[k]) for k in keys)] = r

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for key in sorted(existing):
            w.writerow({k: existing[key].get(k, "") for k in header})


def extract(texts, root, fetched_at):
    """保存済みテキストから3つのCSVを作る。

    各ページを独立して抽出する。一部が失敗しても、他ページで取れた行は保存する。
    戻り値は (四本値件数, 時刻件数, 詳細件数, 抽出エラー一覧)。
    """
    stamp = fetched_at.isoformat(timespec="seconds")
    ohlc, times, detail = [], [], []
    failures = []

    def add_ohlc(name, d, bars):
        ohlc.append(
            {
                "trade_date": d, "name": our_name(name), "fetched_at": stamp,
                **{k: bars.get(k, "") for k in ("open", "high", "low", "close")},
            }
        )

    if "nk225_summary" in texts:
        try:
            s = N.parse_summary(texts["nk225_summary"])
            add_ohlc("日経平均", s["trade_date"], s["ohlc"])
            times.append(
                {
                    "trade_date": s["trade_date"], "name": "日経平均", "fetched_at": stamp,
                    **{f"{k}_time": s["times"].get(k, "") for k in ("open", "high", "low")},
                }
            )
            for group, key, sub, value, unit in s["detail"]:
                detail.append(
                    {
                        "trade_date": s["trade_date"], "group": group, "key": key,
                        "sub": sub, "value": value, "unit": unit, "fetched_at": stamp,
                    }
                )
        except Exception as e:
            failures.append(("日経平均サマリー抽出", str(e).splitlines()[0]))

    for tag, label in (
        ("nk225vi_profile", "日経VIプロフィル抽出"),
        ("nkscd_profile", "日経半導体株指数プロフィル抽出"),
    ):
        if tag not in texts:
            continue
        try:
            p = N.parse_profile(texts[tag])
            add_ohlc(p["name"], p["trade_date"], p["ohlc"])
            times.append(
                {
                    "trade_date": p["trade_date"], "name": our_name(p["name"]), "fetched_at": stamp,
                    **{f"{k}_time": p["times"].get(k, "") for k in ("open", "high", "low")},
                }
            )
        except Exception as e:
            failures.append((label, str(e).splitlines()[0]))

    if "index_list" in texts:
        try:
            found = N.parse_index_list(
                texts["index_list"], LIST_TARGETS, today=fetched_at.date(), strict=False
            )
            missing = [name for name in LIST_TARGETS if name not in found]
            if missing:
                failures.append(("指数一覧抽出", f"一覧に見つからない: {', '.join(missing)}"))
            for name, v in found.items():
                add_ohlc(name, v["trade_date"], {"close": v["close"]})
        except Exception as e:
            failures.append(("指数一覧抽出", str(e).splitlines()[0]))

    # ここまでに一部失敗があっても、集められた行は必ず保存する。
    data = os.path.join(root, "data")
    _merge(os.path.join(data, "nikkei_ohlc.csv"), OHLC_HEADER,
           ["trade_date", "name"], ohlc)
    _merge(os.path.join(data, "nikkei_ohlc_time.csv"), TIME_HEADER,
           ["trade_date", "name"], times)
    _merge(os.path.join(data, "nikkei225_detail.csv"), DETAIL_HEADER,
           ["trade_date", "group", "key", "sub"], detail)
    return len(ohlc), len(times), len(detail), failures


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
    started = now_jst()
    raw_dir = os.path.join(root, "data", "raw", started.strftime("%Y-%m-%d"))

    ok, errors, warnings, texts = [], [], [], {}
    with browser_session() as read:
        for key in keys:
            label, url = TARGETS[key]
            try:
                text = read(url)

                # 日経平均サマリーはPER/PBR等が後から埋まることがある。
                # 「-」のままなら少し待ってページを取り直す。
                if key == "nk225_summary" and _summary_details_incomplete(text):
                    for attempt in range(1, SUMMARY_RETRIES + 1):
                        print(
                            f"WAIT {key:<16} 詳細データが未反映。"
                            f"{SUMMARY_RETRY_WAIT}秒待って再取得 {attempt}/{SUMMARY_RETRIES}"
                        )
                        time.sleep(SUMMARY_RETRY_WAIT)
                        text = read(url)
                        if not _summary_details_incomplete(text):
                            print(f"OK   {key:<16} 詳細データ再取得成功")
                            break
                    if _summary_details_incomplete(text):
                        warnings.append(
                            "日経平均サマリー: PER/PBR/利回り等が「-」のまま。"
                            "rawは保存し、取得できた価格・他指数は保存する"
                        )

                # テキストは小さく、GitHub 上でそのまま読めるので圧縮しない
                path = os.path.join(raw_dir, f"nkindex_{key}.txt")
                save_raw(path, text)
                texts[key] = text
                ok.append(key)
                print(
                    f"OK   {key:<16} {len(text):>7,}文字 / "
                    f"{text.count(chr(10)) + 1:>4}行  -> {os.path.relpath(path, root)}"
                )
            except Exception as e:
                reason = str(e).splitlines()[0]
                errors.append((f"{label} ({key})", reason))
                print(f"FAIL {key:<16} {reason[:80]}")

    if texts:
        try:
            n_ohlc, n_time, n_detail, extract_errors = extract(texts, root, started)
            errors.extend(extract_errors)
            print(
                f"\n抽出: 四本値 {n_ohlc}件 / 時刻 {n_time}件 / 日経平均詳細 {n_detail}件"
            )
        except Exception as e:
            errors.append(("CSV保存", str(e).splitlines()[0]))
            print(f"FAIL CSV保存  {str(e).splitlines()[0][:80]}")

    if warnings:
        print("\n警告:")
        for msg in warnings:
            print(f"  - {msg}")

    return report(ok, errors, "日経指数ページ取得")


if __name__ == "__main__":
    sys.exit(main(sys.argv))
