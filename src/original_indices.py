"""10のオリジナル指数の定義と構成銘柄ルール。"""

from collections import defaultdict


ORIGINAL_INDEXES = [
    {
        "id": 1,
        "name": "ブルジョワ地主指数",
        "concept": "富からカネを生む",
        "definition": "土地・金融資産・運用資産など、既に保有する富を働かせ、賃料・利ざや・手数料・運用益を得る企業群。",
    },
    {
        "id": 2,
        "name": "政治寄生指数",
        "concept": "政府のカネとルールに寄生する",
        "definition": "政府予算、公共調達、補助制度、法令・規制によって生まれる義務的需要から収益を得る企業群。",
    },
    {
        "id": 3,
        "name": "中抜きピンハネ指数",
        "concept": "中抜きとピンハネで利益を取る",
        "definition": "人・商品・取引・情報の商流に入り、仲介料、派遣マージン、プラットフォーム手数料などを得る企業群。",
    },
    {
        "id": 4,
        "name": "ライフライン占有指数",
        "concept": "生活インフラから利益を取る",
        "definition": "通信、電力・ガス、交通、警備など、生活に不可欠で継続利用される基盤から収益を得る企業群。",
    },
    {
        "id": 5,
        "name": "日銭商い指数",
        "concept": "日常消費から利益を取る",
        "definition": "食品、日用品、小売、外食など、庶民の少額・高頻度の日常支出から収益を得る企業群。",
    },
    {
        "id": 6,
        "name": "ハードグッズ指数",
        "concept": "庶民の耐久消費・大型支出から利益を取る",
        "definition": "住宅、住宅設備、家電、家具、大衆車など、庶民の高額・低頻度の耐久消費・大型支出から収益を得る企業群。",
    },
    {
        "id": 7,
        "name": "自己顕示欲指数",
        "concept": "高級品・贅沢品から利益を取る",
        "definition": "高級品、ブランド、化粧品、百貨店、贅沢な体験など、非必需の高単価・高粗利消費から収益を得る企業群。",
    },
    {
        "id": 8,
        "name": "脳Hack指数",
        "concept": "時間と集中力から利益を取る",
        "definition": "SNS、広告、ゲーム、動画、メディアなど、利用者の可処分時間と集中力を集めて収益化する企業群。",
    },
    {
        "id": 9,
        "name": "テクノロジー指数",
        "concept": "技術を売る",
        "definition": "製造装置、電子部品、特殊素材、FA、精密機器など、不可欠な技術・特許・工程上の急所を握って収益を得る企業群。",
    },
    {
        "id": 10,
        "name": "ライジングサン指数",
        "concept": "海外で稼ぐ",
        "definition": "海外売上、輸出、海外生産・販売、資源・国際商流などを通じ、海外市場から利益を得る企業群。",
    },
]

STRENGTH_WEIGHT = {"大": 1.0, "中": 0.7, "小": 0.5}
DEMAND_STRENGTH = {"強外需": "大", "外需": "中", "内外均衡": "小"}


def _contains(text, words):
    return any(word in text for word in words)


def classify_original_indices(row):
    """分類行から {指数ID: 大中小} を返す。重複所属を許す。"""
    code = row.get("code", "")
    major = row.get("major", "")
    sector = row.get("sector", "")
    industry = row.get("industry", "")
    demand = row.get("demand", "")
    memberships = {}

    def add(index_id, strength):
        current = memberships.get(index_id)
        if current is None or STRENGTH_WEIGHT[strength] > STRENGTH_WEIGHT[current]:
            memberships[index_id] = strength

    # 1. 金融資本と賃貸資産。住宅を建てて売る会社は下の6へ分ける。
    if major == "金融・金利敏感":
        add(1, "大")
    if _contains(industry, ("不動産開発・賃貸", "倉庫・物流不動産", "駐車場")):
        add(1, "大" if industry == "不動産開発・賃貸" else "中")
    if _contains(industry, ("投資持株", "ベンチャーキャピタル", "取引所")):
        add(1, "大")
    if industry == "総合商社":
        add(1, "小")

    # 2. 公共予算、制度対応、規制による義務需要。
    if _contains(industry, ("インフラ補修", "海洋土木", "防衛", "原子力")):
        add(2, "大")
    if _contains(industry, (
        "総合建設・設備工事", "電力設備工事", "通信設備工事", "空調・設備工事",
        "SI・システム開発", "ITサービス・通信設備", "IT機器販売・SI",
        "サイバーセキュリティ", "医療情報サービス",
    )):
        add(2, "中")
    if _contains(industry, (
        "プラント・エンジニアリング", "ソフトウェアテスト・DX", "企業向けソフトウェア",
        "SaaS", "コンサルティング", "臨床検査",
    )):
        add(2, "小")
    if industry == "電力":
        add(2, "小")

    # 3. 人材、仲介、卸売、取引プラットフォーム。
    if _contains(industry, ("M&A仲介", "人材", "コンサルティング", "中古車オークション")):
        add(3, "大")
    if _contains(industry, (
        "商社", "卸", "決済プラットフォーム", "フリマ・EC", "B2B・EC",
        "通信販売代理", "人材プラットフォーム",
    )):
        add(3, "中")
    if _contains(industry, ("総合物流", "宅配・陸運", "港湾物流", "取引所", "業務・生活サービス")):
        add(3, "小")

    # 4. 回避しにくい通信・エネルギー・交通・警備の継続利用。
    if industry in ("通信キャリア", "電力", "鉄道", "警備") or "都市ガス" in industry:
        add(4, "大")
    if _contains(industry, ("通信・クラウド基盤", "インターネットインフラ", "エレベーター保守", "LPガス")):
        add(4, "中")
    if _contains(industry, ("宅配・陸運", "総合物流", "港湾物流", "郵便")) or industry == "航空":
        add(4, "小")

    # 5. 少額・高頻度の日常消費。
    if _contains(industry, (
        "食品・飲料", "水産・食品原料", "ビール・飲料", "調味料", "食品素材",
        "日用品", "衛生用品", "たばこ", "スーパー", "ドラッグストア・調剤",
        "ディスカウントストア", "外食",
    )):
        add(5, "大")
    if _contains(industry, (
        "菓子・土産", "小売", "生活雑貨・衣料", "衣料・インナー", "育児用品",
        "文具・オフィス用品", "アパレル", "靴・専門店",
    )):
        add(5, "中")
    if _contains(industry, ("化粧品", "衣料・家具専門店")):
        add(5, "小")

    # 6. 住宅・設備・家電・家具・自動車など高額で低頻度の支出。
    if _contains(industry, ("住宅・不動産開発", "住宅・木材", "住宅設備", "民生電機")):
        add(6, "大")
    if _contains(industry, (
        "建築用シャッター", "空調機器", "総合電機・電池", "事務・民生機器",
        "完成車", "衣料・家具専門店", "住宅ローン保証",
    )):
        add(6, "中")
    if _contains(industry, ("二輪・船外機", "自転車部品・釣具", "スポーツ用品", "楽器・音響機器")):
        add(6, "小")

    # 7. 高単価、高粗利、非必需の品物と体験。
    if _contains(industry, ("百貨店", "化粧品", "テーマパーク")):
        add(7, "大")
    if _contains(industry, ("ホテル・宿泊", "レジャー・娯楽", "スポーツアパレル", "キャラクターIP")):
        add(7, "中")
    if _contains(industry, ("菓子・土産", "ファッションEC", "スポーツ用品", "楽器・音響機器", "空港施設・免税店")):
        add(7, "小")

    # 8. 視線と可処分時間そのものを集めて課金・広告へ変える事業。
    if _contains(industry, ("広告", "テレビ・放送", "ゲーム・コンテンツ", "インターネット広告・メディア")):
        add(8, "大")
    if _contains(industry, ("ゲーム・玩具・IP", "キャラクターIP", "遊技機", "業務用カラオケ", "レジャー・娯楽")):
        add(8, "中")
    if _contains(industry, ("インターネットサービス", "フリマ・EC", "ファッションEC", "EC・通信・金融", "テーマパーク")):
        add(8, "小")

    # 9. 技術・特許・製造工程のボトルネック。
    if sector in ("半導体", "ハイテク・電子", "精密・計測", "精密・医療", "非鉄・半導体"):
        add(9, "大")
    if _contains(industry, (
        "半導体", "電子部品", "FA・制御機器", "精密減速機", "空圧制御機器",
        "制御・計測機器", "分析・計測機器", "電子顕微鏡", "光センサー", "医療機器",
    )):
        add(9, "大")
    if sector in ("機械", "電機", "素材", "重工・防衛", "重工・造船", "ハイテク・ヘルスケア"):
        add(9, "中")
    if _contains(industry, (
        "機能性化学", "機能材料", "高機能繊維", "産業ガス", "ガラス・電子材料",
        "化学・機能材料", "創薬基盤", "水処理装置", "工作機械",
        "機械部品", "ボイラー・熱機器", "物流自動化設備", "蓄電池",
        "建築化学材", "断熱・シール材",
    )):
        add(9, "中")
    if "医薬品" in industry and "卸" not in industry:
        add(9, "中")
    if _contains(industry, ("自動車部品", "タイヤ・ゴム", "鉄鋼", "セメント", "炭素製品", "電線・光ファイバー")):
        add(9, "小")
    if _contains(industry, ("サイバーセキュリティ", "ソフトウェアテスト・DX", "SaaS")):
        add(9, "中")

    # 10. 海外で稼ぐ度合いは既存の需要地域タグをそのまま大中小へ置き換える。
    overseas_strength = DEMAND_STRENGTH.get(demand)
    if overseas_strength:
        add(10, overseas_strength)

    # 事業内容が業種名だけでは分かれない銘柄の補正。
    overrides = {
        # 大東建託は土地保有型ではなく、賃貸住宅の建設・管理を主軸として扱う。
        "1878": {1: None, 3: "小", 6: "大"},
        "3288": {1: None, 6: "大"},
        "3291": {1: None, 6: "大"},
        # 野村不動産は賃貸資産と住宅販売を両方持つため重複させる。
        "3231": {6: "中"},
        # 家電量販店と家具販売は、日常小売より大型生活支出を主とする。
        "8282": {5: None, 6: "大"},
        "9831": {5: None, 6: "大"},
        "9843": {5: None, 6: "大"},
        # しまむらは家具ではなく大衆衣料の日常消費として扱う。
        "8227": {5: "大", 6: None},
        # リログループは不動産保有より仲介・管理手数料を主とする。
        "8876": {3: "中"},
        # 研究機器の卸売は、製品技術より商流マージンを主として扱う。
        "7476": {3: "中", 9: "小"},
        # ソニーはコンテンツに加え、プレミアムな耐久消費も一部持つ。
        "6758": {6: "小", 7: "小", 8: "中"},
        # 大衆向けネットサービスのうち、広告・視線の収益化が大きいもの。
        "2371": {8: "中"},
        "4689": {8: "大"},
        "4755": {8: "中"},
    }
    for index_id, strength in overrides.get(code, {}).items():
        if strength is None:
            memberships.pop(index_id, None)
        else:
            add(index_id, strength)

    return memberships


def membership_summary(rows):
    """検査・表示用に指数別の大中小件数を返す。"""
    summary = defaultdict(lambda: defaultdict(int))
    for row in rows:
        for index_id, strength in classify_original_indices(row).items():
            summary[index_id][strength] += 1
    return {index_id: dict(summary[index_id]) for index_id in range(1, 11)}
