"""細かい分類マスターから、相場を見るための集約分類を生成する。

入力: data/stock-sectors-detail.csv
出力: data/stock-sectors.csv

ルール:
- 元の細分類は detail 側に残す。
- 表示・集計用は株価ドライバーが近いものをまとめる。
- セクターも業種も最低3銘柄。1～2銘柄の分類は一切出さない。
- 3銘柄未満が1件でもあれば生成を失敗させる。
- 個別指定された銘柄はコードで集約分類を固定する。
- 需要地域タグは元データを維持し、国内/海外売上比率の差は需要地域側の寄与に使う。
"""

import csv
import os
import sys
from collections import Counter

from common import repo_root

MIN_MEMBERS = 3
BEVERAGE_CODES = {"2501", "2502", "2503", "2579", "2587", "2593"}

# 国内消費 / メディアコンテンツへまとめる指定銘柄。
# 需要地域タグは元データを維持するため、外需比率が高い銘柄を内需指数へ無理に寄与させない。
MEDIA_CONTENT_CODES = {
    "2432",  # DeNA
    "3635",  # コーエーテクモ
    "3659",  # ネクソン
    "6460",  # セガサミー
    "7832",  # バンダイナムコ
    "7974",  # 任天堂
    "8136",  # サンリオ
    "9468",  # KADOKAWA
    "9602",  # 東宝
    "9684",  # スクウェア・エニックス
    "9697",  # カプコン
    "9766",  # コナミ
}

# 外需コンテンツを2銘柄だけのセクターとして残さない。
GLOBAL_CONSUMER_CONTENT_CODES = {
    "6758",  # ソニー
    "7867",  # タカラトミー
}

# ユーザー指定の個別分類。需要地域は元データをそのまま使う。
CLASSIFICATION_OVERRIDES = {
    "2222": ("内需・国内景気", "国内消費", "余剰消費"),       # 寿スピリッツ
    "2914": ("ディフェンシブ・公共", "生活必需品", "食品"),    # JT
    "3038": ("内需・国内景気", "国内消費", "生活小売"),       # 神戸物産
    "3391": ("内需・国内景気", "ヘルスケア", "医療サービス・機器"),  # ツルハ
    "7453": ("内需・国内景気", "国内消費", "余剰消費"),       # 良品計画
    "8252": ("金融・金利敏感", "金融", "クレジット・リース"),    # 丸井
    "9861": ("内需・国内景気", "国内消費", "生活小売"),       # 吉野家
}


def has(text, *words):
    return any(word in text for word in words)


def group_sector(major, raw_sector, industry):
    if major == "外需・グローバル景気":
        if has(industry, "商社") or raw_sector == "卸売":
            return "専門商社"
        if raw_sector in {"自動車", "自動車・機械", "自動車・電子"}:
            return "自動車"
        if raw_sector in {"コンテンツ", "ハイテク・コンテンツ"}:
            return "コンテンツ"
        if raw_sector == "半導体" or (raw_sector == "ハイテク・電子" and has(industry, "半導体材料")):
            return "半導体"
        if raw_sector in {"精密・医療", "精密・計測", "ハイテク・ヘルスケア", "ヘルスケア"}:
            return "精密"
        if raw_sector in {"重工・防衛", "重工・造船"}:
            return "重工・防衛"
        if raw_sector in {"情報通信", "投資・ハイテク"}:
            return "IT・通信"
        if raw_sector in {"ハイテク・電子", "電機"}:
            return "電機・電子"
        if raw_sector == "機械":
            return "機械"
        if raw_sector in {"消費", "消費・機械"}:
            return "グローバル消費"
        if raw_sector in {"素材", "建設・不動産"}:
            return "素材"
        return "素材"

    if major == "資源・市況":
        if raw_sector in {"資源開発", "エネルギー", "機械"}:
            return "エネルギー・資源"
        if raw_sector == "総合商社":
            return "総合商社"
        if raw_sector == "運輸・物流":
            return "海運"
        if raw_sector in {"非鉄・電線", "非鉄・半導体"}:
            return "非鉄・電線"
        if raw_sector == "素材" and has(industry, "鉄鋼"):
            return "鉄鋼"
        if raw_sector == "素材" and has(industry, "非鉄"):
            return "非鉄・電線"
        return "素材・化学"

    if major == "内需・国内景気":
        if raw_sector in {"素材", "食品", "消費", "消費・コンテンツ", "メディア"}:
            return "国内消費"
        if raw_sector == "建設・不動産":
            return "国内建設・不動産"
        if raw_sector in {"情報通信", "ハイテク・電子", "機械"}:
            return "国内情報通信"
        if raw_sector in {"サービス", "卸売"}:
            return "国内サービス"
        if raw_sector in {"運輸・物流", "運輸・不動産", "公共・金融"}:
            return "運輸・物流"
        if raw_sector == "ヘルスケア":
            return "ヘルスケア"
        return "国内サービス"

    if major == "金融・金利敏感":
        return "金融"

    if major == "ディフェンシブ・公共":
        if raw_sector == "消費":
            return "生活必需品"
        if raw_sector == "ヘルスケア":
            return "医薬品"
        if raw_sector == "公益":
            return "公益"
        return raw_sector

    return raw_sector


def group_industry(major, sector, raw_sector, industry, code):
    if major == "外需・グローバル景気":
        if sector == "自動車":
            if has(industry, "タイヤ", "ゴム"):
                return "タイヤ・ゴム"
            if has(industry, "完成車", "二輪", "船外機"):
                return "完成車"
            return "自動車部品"

        if sector == "半導体":
            if has(industry, "製造装置", "搬送装置", "検査", "計測装置", "精密計測"):
                return "半導体製造装置"
            if has(industry, "メモリ", "デバイス"):
                return "半導体デバイス・メモリ"
            return "半導体材料"

        if sector == "精密":
            if has(industry, "医療") or raw_sector in {"ハイテク・ヘルスケア", "ヘルスケア"}:
                return "精密医療"
            return "精密機械"

        if sector == "電機・電子":
            if has(industry, "重電", "電力設備", "蓄電池", "総合電機・電池"):
                return "重電・電池"
            if has(industry, "民生", "事務"):
                return "民生・事務機器"
            return "電子部品・電子機器"

        if sector == "機械":
            if has(industry, "工作機械"):
                return "工作機械"
            if has(industry, "FA", "制御", "減速機", "物流自動化"):
                return "FA・制御"
            return "産業・建設機械"

        if sector == "素材":
            if has(industry, "繊維", "ガラス", "シャッター"):
                return "素材・建材"
            return "化学・機能材料"

        if sector == "重工・防衛":
            return "重工・防衛"
        if sector == "コンテンツ":
            return "ゲーム・コンテンツ"
        if sector == "グローバル消費":
            return "グローバル消費"
        if sector == "IT・通信":
            return "IT・通信"
        if sector == "専門商社":
            return "専門商社"

    if major == "資源・市況":
        if sector == "エネルギー・資源":
            return "石油・ガス・資源"
        if sector == "総合商社":
            return "総合商社"
        if sector == "海運":
            return "海運"
        if sector == "鉄鋼":
            return "鉄鋼"
        if sector == "非鉄・電線":
            return "電線" if has(industry, "電線", "光ファイバー") else "非鉄金属"
        if sector == "素材・化学":
            return "紙・炭素" if has(industry, "紙", "炭素") else "基礎化学"

    if major == "内需・国内景気":
        if sector == "国内建設・不動産":
            if has(industry, "住宅・不動産開発", "住宅・木材", "住宅設備"):
                return "住宅系"
            if has(industry, "不動産開発・賃貸", "駐車場"):
                return "不動産"
            if has(industry, "電力設備工事", "通信設備工事", "空調・設備工事"):
                return "建設設備"
            return "インフラ系"

        if sector == "国内消費":
            if raw_sector == "メディア":
                return "メディアコンテンツ"
            if has(industry, "遊技機", "カラオケ", "レジャー", "娯楽", "テーマパーク"):
                return "レジャー娯楽"
            if has(industry,
                   "外食", "百貨店", "ファッションEC", "化粧品", "ホテル", "宿泊"):
                return "余剰消費"
            return "生活小売"

        if sector == "国内情報通信":
            if has(industry,
                   "通信キャリア", "通信・クラウド", "通信設備", "通信販売代理",
                   "インターネットインフラ", "クラウド基盤"):
                return "通信インフラ"
            if has(industry,
                   "インターネットサービス", "フリマ", "決済", "EC・通信・金融",
                   "インターネット広告", "メディア"):
                return "B2C"
            return "B2B"

        if sector == "国内サービス":
            return "サービス"

        if sector == "運輸・物流":
            if has(industry, "鉄道"):
                return "鉄道"
            if has(industry, "航空", "空港"):
                return "航空・空港"
            return "陸運・物流"

        if sector == "ヘルスケア":
            if has(industry, "医薬品卸"):
                return "医薬品卸"
            return "医療サービス・機器"

    if major == "金融・金利敏感":
        if industry == "メガバンク":
            return "メガバンク"
        if has(industry, "銀行"):
            return "他銀行"
        if industry == "リース" or has(industry, "クレジット", "消費者金融"):
            return "クレジット・リース"
        if has(industry, "生命保険", "損害保険"):
            return "生損保"
        if has(industry, "証券", "取引所"):
            return "証券"
        return "他金融"

    if major == "ディフェンシブ・公共":
        if sector == "生活必需品":
            if code in BEVERAGE_CODES or has(industry, "ビール・飲料", "清涼飲料"):
                return "飲料"
            if has(industry, "日用品", "衛生用品", "育児用品", "ヘルスケア", "たばこ"):
                return "日用品"
            return "食品"
        if sector == "医薬品":
            return "医薬品"
        if sector == "公益":
            if has(industry, "ガス", "LPガス"):
                return "ガス"
            return "電力"

    return industry


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def transform(rows):
    out = []
    source_codes = set()
    for r in rows:
        code = (r.get("code") or "").strip().upper()
        major = (r.get("major") or "").strip()
        raw_sector = (r.get("sector") or "").strip()
        raw_industry = (r.get("industry") or "").strip()
        demand = (r.get("demand") or "").strip()
        if not code or not major or not raw_sector or not raw_industry:
            continue
        source_codes.add(code)

        if code in MEDIA_CONTENT_CODES:
            major = "内需・国内景気"
            sector = "国内消費"
            industry = "メディアコンテンツ"
        elif code in GLOBAL_CONSUMER_CONTENT_CODES:
            major = "外需・グローバル景気"
            sector = "グローバル消費"
            industry = "グローバル消費"
        elif code in CLASSIFICATION_OVERRIDES:
            major, sector, industry = CLASSIFICATION_OVERRIDES[code]
        else:
            sector = group_sector(major, raw_sector, raw_industry)
            industry = group_industry(major, sector, raw_sector, raw_industry, code)

        out.append({
            "code": code,
            "major": major,
            "sector": sector,
            "industry": industry,
            "demand": demand,
        })

    missing_media = sorted(MEDIA_CONTENT_CODES - source_codes)
    if missing_media:
        print("指定メディア銘柄が詳細分類にない: " + ", ".join(missing_media), file=sys.stderr)
    return out


def validate(rows):
    errors = []
    sector_counts = Counter((r["major"], r["sector"]) for r in rows)
    industry_counts = Counter((r["major"], r["sector"], r["industry"]) for r in rows)

    for (major, sector), count in sorted(sector_counts.items()):
        if count < MIN_MEMBERS:
            errors.append(f"セクター {major} / {sector}: {count}銘柄")
    for (major, sector, industry), count in sorted(industry_counts.items()):
        if count < MIN_MEMBERS:
            errors.append(f"業種 {major} / {sector} / {industry}: {count}銘柄")

    forbidden = {
        "運輸・不動産", "消費・コンテンツ", "国内素材", "遊技機",
        "建設・不動産", "サービス・卸売", "建設・土木", "設備工事", "住宅・建材",
        "余剰小売", "外食", "食品・生活用品", "ディフェンシブ消費", "奢侈品", "生活品",
        "レジャー・娯楽", "メディア", "コンテンツ", "リース", "クレジット",
    }
    for r in rows:
        if r["sector"] in forbidden or r["industry"] in forbidden:
            errors.append(f"禁止された細分類が残存: {r['code']} {r['sector']} / {r['industry']}")
        if r["major"] == "内需・国内景気" and r["sector"] == "国内サービス" and r["industry"] != "サービス":
            errors.append(f"国内サービスの分割が残存: {r['code']} / {r['industry']}")

    media_rows = [r for r in rows if r["code"] in MEDIA_CONTENT_CODES]
    for r in media_rows:
        if (r["major"], r["sector"], r["industry"]) != ("内需・国内景気", "国内消費", "メディアコンテンツ"):
            errors.append(f"メディア指定銘柄の分類不一致: {r['code']} {r['major']} / {r['sector']} / {r['industry']}")

    if errors:
        print("分類生成エラー（3銘柄未満または禁止分類）:", file=sys.stderr)
        for e in errors:
            print("  " + e, file=sys.stderr)
        return False

    print(f"集約分類: {len(rows)}銘柄 / セクター {len(sector_counts)} / 業種 {len(industry_counts)}")
    for major in sorted({r['major'] for r in rows}):
        print(f"  {major}")
        sectors = sorted((s, c) for (m, s), c in sector_counts.items() if m == major)
        for sector, count in sectors:
            inds = sorted((i, c) for (m, s, i), c in industry_counts.items() if m == major and s == sector)
            detail = " / ".join(f"{i}:{c}" for i, c in inds)
            print(f"    {sector}:{count} -> {detail}")
    return True


def main():
    root = repo_root()
    src = os.path.join(root, "data", "stock-sectors-detail.csv")
    dst = os.path.join(root, "data", "stock-sectors.csv")
    if not os.path.exists(src):
        print(f"詳細分類がない: {src}", file=sys.stderr)
        return 2

    rows = transform(read_rows(src))
    if not validate(rows):
        return 3

    with open(dst, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "major", "sector", "industry", "demand"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
