/* サイトのAI分析を受けて Gemini に投げ、文章を返す中継。 */
const MAX_BODY = 96 * 1024;
const MAX_SUBS = 10;
const RATE_LIMIT = 6;
const RATE_WINDOW = 60 * 1000;
const seen = new Map();

function tooOften(ip) {
  const now = Date.now();
  const hits = (seen.get(ip) || []).filter((t) => now - t < RATE_WINDOW);
  hits.push(now);
  seen.set(ip, hits);
  if (seen.size > 5000) seen.clear();
  return hits.length > RATE_LIMIT;
}

function corsHeaders(origin, allowed) {
  const ok = !allowed.length || allowed.includes(origin);
  return {
    "access-control-allow-origin": ok && origin ? origin : (allowed[0] || "*"),
    "access-control-allow-methods": "GET, POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    "access-control-max-age": "86400"
  };
}

function reply(status, obj, headers) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", ...headers }
  });
}

const RULES = `次のJSONは、ある銘柄（main）と、その相関の相手（subs）について、
プログラムが計算した数字です。この数字だけを使って日本語で述べてください。

守ること
- JSONに無いことは書かない。会社の事情や出来事は知らないものとして扱う
- 相関を因果として書かない。連動しているという以上のことは言わない
- 材料が足りない項目は、足りないと書く
- 箇条書きを主に、全体で600字程度

書く順
1. メイン銘柄が今どういう状態か（ret / hv20 / ma200Gap / drawdown / rangePos）
2. 相関の強い相手と、その相関が今は強いのか弱いのか（r / r60Ago / r60Rank / r60Path）
3. メインの局面による違い（regime.up と regime.down の差が大きい相手）
4. 条件付きの傾向（cond と fwd。base との差が小さければ「差がない」と書く）
5. 先行しているように見える相手（lead）

数字の読み方
- unit が "%" なら百分率、"pt" なら金利などの前日差でポイント
- n は計算に使った観測の数。少ないものは弱い材料として扱う
- regime … メインの直前20観測の累積がプラスだった日とマイナスだった日で分けた相関
- cond … サブが上がった日／下がった日の、メインの1日あたり平均と勝率。base は全日
- fwd … サブの直近20観測の累積が上位25%／下位25%だった後の、メイン20観測ぶんの成績。base は全体
- lead … サブを何観測ずらしたときの相関か。正なら「サブが先、メインが後」。0 が同時
- r60Path … [年月, 60日相関] を古い順に間引いたもの`;

const TECH_RULES = `次のJSONは、ある銘柄（name）について、プログラムが計算した
テクニカル指標と、主要指数などとの相関です。この数字だけを使って日本語で述べてください。

守ること
- JSONに無いことは書かない。会社の事情や出来事は知らないものとして扱う
- 過去に似た局面があったという話を、これからそうなるという話にしない
- 材料が足りない項目は、足りないと書く
- 使った期間（span）に必ず触れる。何年ぶんを見て言っているのかを最初に書く
- 見出しと箇条書きで、本文は1200字程度。そのあとに点数を付ける

書く順
1. 何年ぶんを見たか（span）。params.base が既定の数字、params.tuned がこの銘柄に合わせて選び直した数字。両方を並べて、違いが大きい指標があれば触れる
2. 長期のトレンド … base と tuned の移動平均・移動平均乖離、slope2 / order / chg100 / chg200 / pos52 / dev2
3. 短期のトレンド … tuned.recent の chg5 / chg10 / dev0 / rsi / stK / stD / macdH / macdHR / bbB / run / gap / range
4. 指標ごとの状態と経緯 … tuned.back の 20/40/60/80/100/150/200日前と今を比べる。dMaS / dMaL / dMacd / dSar / dStoch / dRsi はその向きになってからの日数
5. 似た局面（like.short と like.long）… いつのことか、そのとき指標がどうで、その後どうだったか（after の median と win）。件数（n）が少なければ弱いと書く
6. 相関（corr）… 連動している相手と、その相関が今は強いのか弱いのか。相関を因果として書かない
7. 長期と短期で向きが食い違っているなら、そのことをはっきり書く
8. 最後に「AI主観コメント」として点数を付ける

点数の付け方
50が中立、100が超ストロングバイ、0がストロングセル。「○○/100」の形で次の9つを出し、各行に理由を添える。

AI主観コメント
トレンド系      長期 ○○/100  短期 ○○/100  超短期 ○○/100
オシレーター系  長期 ○○/100  短期 ○○/100  超短期 ○○/100
総合            長期 ○○/100  短期 ○○/100  超短期 ○○/100

- 長期 … 200日前後　短期 … 60日以内　超短期 … 20日以内
- トレンド系 … 移動平均・乖離・並び（order）・傾き（slope）・パラボリック・MACD・騰落率
- オシレーター系 … RSI・ストキャス・RCI・%B（bbB）
- 材料が足りない期間は点を付けず「材料が足りない」と書く

数字の読み方
- 単位は % が主。dev は移動平均からの乖離%、slope は移動平均の傾き%
- order は移動平均の並び（＋が短期→長期の順、−が逆）
- bbB は %B、bbW はバンド幅%。pos52 は52週レンジの中の位置%、posDay はその日の値幅の中の位置%
- macdHR は MACDヒストグラム÷株価%。atr は ATR%、hv は年率換算のばらつき%
- volR は出来高÷20日平均%。無い銘柄では null
- run は連騰連落の日数（＋が連騰、−が連落）
- like.hits の dist は今との近さ（0 に近いほど似ている）。fwd はその日から5/10/20/60日後の騰落率%
- corr の中身は相関の計算結果。r が相関、r60Ago は60日前の値、regime はメインが上げていた局面と下げていた局面で分けた相関
- null は計算できなかったところ`;

const MARKET_RULES = `次のJSONは、本日の日本株についてプログラムが集めた市況データです。このJSONにある数字だけを使って、日本語で本日の市況を解説してください。

守ること
- JSONに無いニュース、企業材料、政策発言、需給事情を作らない
- 同時に動いたというだけで因果関係を断定しない。「影響した可能性」「整合的」「数字だけでは断定できない」と区別する
- 観測事実と解釈を混同しない
- 日付が違う市場を比較するときは dataDate / prevDate を確認する。米国株は日本株より前の確定セッションが材料になり得る
- 金利は騰落率ではなく levelPct と changeBp（bp変化）で読む
- missing=true の項目は補わず「データなし」とする
- セクター・業種の騰落率は構成銘柄の単純平均で、時価総額加重ではない
- 需要地域は、強内需/強外需=1.0、内需/外需=0.5で集計した指数である

書く順
1. 本日の日本株全体：日経平均、TOPIX、規模別、大分類、需要地域から地合いを要約
2. 上昇業種：上位5業種と構成銘柄の騰落率を見て、何が押し上げたか、共通項があるかを述べる。1銘柄だけの突出なら明記
3. 下落業種：下位5業種も同様に、下落が広いのか特定銘柄主導なのかを見る
4. 物色の共通項：外需/内需、景気敏感/ディフェンシブ、金融、半導体、消費など、実際の上位・下位から共通する傾向を抽出
5. 海外・マクロとの関係：NYダウ、S&P500、NASDAQ、NASDAQ100、Russell2000、SOX、KOSPI、ドル円、米10年金利、日本10年金利を照合し、日本株と整合する点・しない点を分ける。特に半導体、金利敏感株、外需株への影響を検討
6. 最後に「今日の相場を一言」で、最も特徴的だったローテーションまたは集中度を1～2文でまとめる

本文は1500～2200字程度。見出しと箇条書きを使い、数字を具体的に示す。`;

async function callGemini(env, payload, rules) {
  const model = env.GEMINI_MODEL || "gemini-3.1-pro-preview";
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: `${rules}\n\n${JSON.stringify(payload)}` }] }],
      generationConfig: {
        temperature: 0.2,
        maxOutputTokens: 7000,
        thinkingConfig: { thinkingBudget: 3500 }
      }
    })
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`Gemini HTTP ${res.status}\n${text.slice(0, 800)}`);
  let json;
  try { json = JSON.parse(text); }
  catch (e) { throw new Error(`Gemini の返しが読めない\n${text.slice(0, 800)}`); }
  const parts = json?.candidates?.[0]?.content?.parts || [];
  const answer = parts.map((p) => p.text || "").join("").trim();
  if (!answer) throw new Error(`Gemini が本文を返さなかった\n${text.slice(0, 800)}`);
  return answer;
}

const MAX_CODES = 10;
async function askJquants(request, env, cors) {
  if (!env.GH_TOKEN) return reply(500, { error: "GH_TOKEN が入っていない" }, cors);
  if (!env.GH_REPO) return reply(500, { error: "GH_REPO が入っていない" }, cors);
  let payload;
  try { payload = JSON.parse(await request.text()); }
  catch (e) { return reply(400, { error: "JSONとして読めない" }, cors); }
  if (env.JQ_PASS && String(payload.pass || "") !== env.JQ_PASS) return reply(403, { error: "合言葉が違う" }, cors);
  const codes = String(payload.codes || "").toUpperCase().split(/[,\s]+/).map((s) => s.trim()).filter(Boolean);
  if (!codes.length) return reply(400, { error: "株価コードが要る" }, cors);
  if (codes.length > MAX_CODES) return reply(400, { error: `一度に${MAX_CODES}銘柄まで` }, cors);
  const bad = codes.find((c) => !/^[0-9A-Z]{4,5}$/.test(c));
  if (bad) return reply(400, { error: `株価コードとして読めない: ${bad}` }, cors);
  const date = /^\d{4}-\d{2}-\d{2}$/;
  const from = date.test(payload.from || "") ? payload.from : "";
  const to = date.test(payload.to || "") ? payload.to : "";
  const res = await fetch(`https://api.github.com/repos/${env.GH_REPO}/dispatches`, {
    method: "POST",
    headers: { authorization:`Bearer ${env.GH_TOKEN}`, accept:"application/vnd.github+json", "content-type":"application/json", "user-agent":"soba-jquants" },
    body: JSON.stringify({ event_type:"jquants", client_payload:{ codes:codes.join(" "), from, to } })
  });
  if (res.status !== 204) {
    const text = await res.text();
    return reply(502, { error:`GitHub が受け取らなかった (${res.status})\n${text.slice(0,300)}` }, cors);
  }
  return reply(200, { ok:true, repo:env.GH_REPO, codes }, cors);
}

export default {
  async fetch(request, env) {
    const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
    const origin = request.headers.get("origin") || "";
    const cors = corsHeaders(origin, allowed);
    if (request.method === "OPTIONS") return new Response(null, { status:204, headers:cors });
    if (allowed.length && !allowed.includes(origin)) return reply(403, { error:`送り元が許可されていない: ${origin || "（無し）"}` }, cors);
    const path = new URL(request.url).pathname.replace(/\/+$/, "");
    if (path === "/prompt") {
      if (request.method !== "GET") return reply(405, { error:"GET のみ" }, cors);
      return new Response(TECH_RULES, { status:200, headers:{ "content-type":"text/plain; charset=utf-8", "cache-control":"no-store", ...cors } });
    }
    if (request.method !== "POST") return reply(405, { error:"POST のみ" }, cors);
    const ipFirst = request.headers.get("cf-connecting-ip") || "unknown";
    if (path === "/jquants") {
      if (tooOften(ipFirst)) return reply(429, { error:`混み合っている。1分に${RATE_LIMIT}回まで` }, cors);
      try { return await askJquants(request, env, cors); }
      catch (e) { return reply(502, { error:String(e && e.message ? e.message : e) }, cors); }
    }
    if (!env.GEMINI_API_KEY) return reply(500, { error:"GEMINI_API_KEY が入っていない" }, cors);
    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    if (tooOften(ip)) return reply(429, { error:`混み合っている。1分に${RATE_LIMIT}回まで` }, cors);
    const body = await request.text();
    if (body.length > MAX_BODY) return reply(413, { error:`送られた数字が大きすぎる（${body.length}バイト）` }, cors);
    let payload;
    try { payload = JSON.parse(body); }
    catch (e) { return reply(400, { error:"JSONとして読めない" }, cors); }

    let rules = RULES;
    if (payload && payload.kind === "market") {
      if (!payload.asOf || !payload.japanMarket || !payload.indices) return reply(400, { error:"asOf / japanMarket / indices が要る" }, cors);
      rules = MARKET_RULES;
    } else if (payload && payload.kind === "tech") {
      if (!payload.tuned || !payload.span) return reply(400, { error:"tuned と span が要る" }, cors);
      rules = TECH_RULES;
    } else if (!payload || !payload.main || !Array.isArray(payload.subs) || !payload.subs.length) {
      return reply(400, { error:"main と subs が要る" }, cors);
    } else if (payload.subs.length > MAX_SUBS) {
      return reply(400, { error:`サブは${MAX_SUBS}銘柄まで` }, cors);
    }

    try { return reply(200, { text:await callGemini(env, payload, rules) }, cors); }
    catch (e) { return reply(502, { error:String(e && e.message ? e.message : e) }, cors); }
  }
};