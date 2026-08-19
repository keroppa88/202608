/* 相関ページの「AI分析開始」を受けて Gemini に投げ、文章を返すだけの中継。
 *
 * ここでやること
 *   - 送り元の確認と回数制限
 *   - 受け取った数字にプロンプトを添えて Gemini に渡す
 *   - 返ってきた文章をそのまま返す
 *
 * ここでやらないこと
 *   - 数字の計算。それはページ側（correlation.js）で済ませてある
 *   - 失敗の握りつぶし。失敗したら、その内容をそのまま返す
 *
 * 必要なもの
 *   GEMINI_API_KEY    wrangler secret put GEMINI_API_KEY で入れる
 *   GEMINI_MODEL      任意。既定は gemini-2.5-flash
 *   ALLOWED_ORIGINS   カンマ区切り。空なら送り元を見ない
 */

const MAX_BODY = 64 * 1024;   // これより大きい体は受けない
const MAX_SUBS = 10;
const RATE_LIMIT = 6;         // 1分あたり
const RATE_WINDOW = 60 * 1000;

// 同じ実体が生きている間だけ効く簡易な制限。取りこぼしはある
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
    "access-control-allow-methods": "POST, OPTIONS",
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
- lead … サブを何観測ずらしたときの相関か。正なら「サブが先、メインが後」。
  0 が同時で、これと比べて大きいずらし方があるかを見る
- r60Path … [年月, 60日相関] を古い順に間引いたもの`;

async function callGemini(env, payload) {
  const model = env.GEMINI_MODEL || "gemini-2.5-flash";
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
    body: JSON.stringify({
      contents: [{ role: "user", parts: [{ text: `${RULES}\n\n${JSON.stringify(payload)}` }] }],
      generationConfig: { temperature: 0.2, maxOutputTokens: 1600 }
    })
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`Gemini HTTP ${res.status}\n${text.slice(0, 800)}`);
  let json;
  try {
    json = JSON.parse(text);
  } catch (e) {
    throw new Error(`Gemini の返しが読めない\n${text.slice(0, 800)}`);
  }
  const parts = json?.candidates?.[0]?.content?.parts || [];
  const answer = parts.map((p) => p.text || "").join("").trim();
  if (!answer) throw new Error(`Gemini が本文を返さなかった\n${text.slice(0, 800)}`);
  return answer;
}

export default {
  async fetch(request, env) {
    const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
    const origin = request.headers.get("origin") || "";
    const cors = corsHeaders(origin, allowed);

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST") return reply(405, { error: "POST のみ" }, cors);
    if (allowed.length && !allowed.includes(origin)) {
      return reply(403, { error: `送り元が許可されていない: ${origin || "（無し）"}` }, cors);
    }
    if (!env.GEMINI_API_KEY) return reply(500, { error: "GEMINI_API_KEY が入っていない" }, cors);

    const ip = request.headers.get("cf-connecting-ip") || "unknown";
    if (tooOften(ip)) return reply(429, { error: `混み合っている。1分に${RATE_LIMIT}回まで` }, cors);

    const body = await request.text();
    if (body.length > MAX_BODY) {
      return reply(413, { error: `送られた数字が大きすぎる（${body.length}バイト）` }, cors);
    }
    let payload;
    try {
      payload = JSON.parse(body);
    } catch (e) {
      return reply(400, { error: "JSONとして読めない" }, cors);
    }
    if (!payload || !payload.main || !Array.isArray(payload.subs) || !payload.subs.length) {
      return reply(400, { error: "main と subs が要る" }, cors);
    }
    if (payload.subs.length > MAX_SUBS) {
      return reply(400, { error: `サブは${MAX_SUBS}銘柄まで` }, cors);
    }

    try {
      return reply(200, { text: await callGemini(env, payload) }, cors);
    } catch (e) {
      return reply(502, { error: String(e && e.message ? e.message : e) }, cors);
    }
  }
};
