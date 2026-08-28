(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const SEP = "\u0001";
  let busy = false;
  let lastSnapshot = null;

  const MARKET_RULES = `次のJSONは、本日の日本株についてプログラムが集めた市況データです。このJSONにある数字だけを使って、日本語で本日の市況を解説してください。

守ること
- JSONに無いニュース、企業材料、政策発言、需給事情を作らない。
- 同時に動いたというだけで因果関係を断定しない。「影響した可能性」「整合的」「数字だけでは断定できない」と区別する。
- observed（観測事実）と interpretation（解釈）を混同しない。
- 日付が違う市場を比較するときは dataDate / prevDate を確認する。米国株は日本株より前の確定セッションが材料になり得る。
- 金利は騰落率ではなく levelPct と changeBp（bp変化）で読む。
- missing=true の項目は無理に補わず「データなし」とする。
- セクター・業種の騰落率は構成銘柄の単純平均。時価総額加重ではない。
- 需要地域は、強内需/強外需=1.0、内需/外需=0.5で集計した指数である。

解説する順
1. 本日の日本株全体：日経平均、TOPIX、規模別、大分類、需要地域から地合いを要約。
2. 上昇業種：上位5業種と構成銘柄の騰落率を見て、何が押し上げたか、共通項があるかを述べる。1銘柄だけの突出ならそのことを書く。
3. 下落業種：下位5業種も同様に、下落が広いのか特定銘柄主導なのかを見る。
4. 物色の共通項：外需/内需、景気敏感/ディフェンシブ、金融、半導体、消費など、実際の上位・下位から共通する傾向を抽出する。
5. 海外・マクロとの関係：NYダウ、S&P500、NASDAQ、NASDAQ100、Russell2000、SOX、KOSPI、ドル円、米10年金利、日本10年金利を照合し、日本株の動きと整合する点・しない点を分ける。特に半導体、金利敏感株、外需株への影響を検討する。
6. 最後に「今日の相場を一言」で、最も特徴的だったローテーションまたは集中度を1～2文でまとめる。

本文は1500～2200字程度。見出しと箇条書きを使い、数字を具体的に示してください。`;

  function esc(v) {
    return String(v == null ? "" : v)
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  }

  function num(v) {
    if (v == null || v === "") return null;
    const n = Number(String(v).replaceAll(",", "").replace("%", "").trim());
    return Number.isFinite(n) ? n : null;
  }

  function round(v, d) {
    const n = num(v);
    if (n == null) return null;
    const p = 10 ** (d == null ? 4 : d);
    return Math.round(n * p) / p;
  }

  function parseCsv(text) {
    const rows = [];
    let row = [], field = "", quoted = false;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quoted) {
        if (ch === '"') {
          if (text[i + 1] === '"') { field += '"'; i++; }
          else quoted = false;
        } else field += ch;
      } else if (ch === '"') quoted = true;
      else if (ch === ",") { row.push(field); field = ""; }
      else if (ch === "\n") {
        row.push(field.replace(/\r$/, "")); field = "";
        if (row.some((v) => v !== "")) rows.push(row);
        row = [];
      } else field += ch;
    }
    if (field !== "" || row.length) {
      row.push(field.replace(/\r$/, ""));
      if (row.some((v) => v !== "")) rows.push(row);
    }
    if (!rows.length) return [];
    const head = rows[0].map((v) => v.replace(/^\uFEFF/, ""));
    return rows.slice(1).map((cells) => {
      const out = {};
      head.forEach((h, i) => { out[h] = cells[i] == null ? "" : cells[i]; });
      return out;
    });
  }

  async function fetchText(path, optional) {
    try {
      const r = await fetch(`${path}?t=${Date.now()}`, { cache:"no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.text();
    } catch (e) {
      if (optional) return null;
      throw new Error(`${path}: ${e && e.message ? e.message : e}`);
    }
  }

  async function fetchJson(path) {
    const r = await fetch(`${path}?t=${Date.now()}`, { cache:"no-store" });
    if (!r.ok) throw new Error(`${path}: HTTP ${r.status}`);
    return r.json();
  }

  function marketRows(rows) {
    return (rows || []).map((r) => ({
      name:String(r.name || ""), change:round(r.change, 4), count:Number(r.count) || 0,
      marketCapTrillion:round(r.marketCapTrillion, 4),
      major:r.major || undefined, sector:r.sector || undefined,
      breakdown:r.breakdown || undefined
    }));
  }

  function latestPair(rows, dateKey, valueKey, asOf) {
    const vals = rows.map((r) => ({ d:String(r[dateKey] || "").slice(0, 10), v:num(r[valueKey]) }))
      .filter((r) => r.d && r.v != null && (!asOf || r.d <= asOf))
      .sort((a, b) => a.d.localeCompare(b.d));
    if (!vals.length) return null;
    const now = vals[vals.length - 1], prev = vals.length > 1 ? vals[vals.length - 2] : null;
    return { now, prev };
  }

  function priceMetric(name, pair, source) {
    if (!pair || !pair.now || !pair.prev || pair.prev.v === 0) return { name, source, missing:true };
    return {
      name, source, dataDate:pair.now.d, prevDate:pair.prev.d,
      level:round(pair.now.v, 6), prev:round(pair.prev.v, 6),
      changePct:round((pair.now.v / pair.prev.v - 1) * 100, 4)
    };
  }

  function yieldMetric(name, pair, source) {
    if (!pair || !pair.now || !pair.prev) return { name, source, missing:true };
    return {
      name, source, dataDate:pair.now.d, prevDate:pair.prev.d,
      levelPct:round(pair.now.v, 4), prevPct:round(pair.prev.v, 4),
      changeBp:round((pair.now.v - pair.prev.v) * 100, 2)
    };
  }

  function parseNikkeiJgb(text, asOf) {
    if (!text) return { name:"日本10年国債", source:"Nikkei市場ページ", missing:true };
    const lines = text.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
    const i = lines.findIndex((s) => s.startsWith("長期金利(％)"));
    if (i < 0) return { name:"日本10年国債", source:"Nikkei市場ページ", missing:true };
    const dateText = lines[i + 1] || "";
    const level = num(lines[i + 2]);
    const diff = num(lines[i + 3]);
    if (level == null || diff == null) return { name:"日本10年国債", source:"Nikkei市場ページ", missing:true };
    const m = dateText.match(/(\d{1,2})\/(\d{1,2})/);
    const year = Number(String(asOf || "").slice(0, 4)) || new Date().getFullYear();
    const dataDate = m ? `${year}-${String(m[1]).padStart(2,"0")}-${String(m[2]).padStart(2,"0")}` : asOf;
    return { name:"日本10年国債", source:"Nikkei市場ページ", dataDate, levelPct:round(level,4), changeBp:round(diff * 100,2) };
  }

  async function mapLimit(items, limit, worker) {
    const out = new Array(items.length);
    let next = 0;
    async function run() {
      while (true) {
        const i = next++;
        if (i >= items.length) return;
        try { out[i] = await worker(items[i], i); }
        catch (e) { out[i] = null; }
      }
    }
    await Promise.all(Array.from({ length:Math.min(limit, items.length || 1) }, run));
    return out;
  }

  function stockChange(text, targetDate) {
    const vals = parseCsv(text).map((r) => ({
      d:String(r.Date || r.date || "").slice(0,10),
      v:num(r.Close != null && r.Close !== "" ? r.Close : r.close)
    })).filter((r) => r.d && r.v != null && r.d <= targetDate)
      .sort((a,b) => a.d.localeCompare(b.d));
    const i = vals.findIndex((r) => r.d === targetDate);
    if (i <= 0 || vals[i-1].v === 0) return null;
    return round((vals[i].v / vals[i-1].v - 1) * 100, 4);
  }

  async function collectIndustryStocks(data, top, worst, progress) {
    progress("上位・下位業種の構成銘柄を集めています…");
    const [classText, listText, capText] = await Promise.all([
      fetchText("data/stock-sectors.csv"), fetchText("data/stocks/list.csv"), fetchText("data/market_cap.csv")
    ]);
    const names = new Map(parseCsv(listText).map((r) => [String(r.code || "").trim().toUpperCase(), String(r.name || "").trim()]));
    const caps = new Map(parseCsv(capText).map((r) => [String(r.code || "").trim().toUpperCase(), num(r.market_cap_million)]));
    const byIndustry = new Map();
    parseCsv(classText).forEach((r) => {
      const key = `${r.major || ""}${SEP}${r.sector || ""}${SEP}${r.industry || ""}`;
      if (!byIndustry.has(key)) byIndustry.set(key, []);
      byIndustry.get(key).push({ code:String(r.code || "").trim().toUpperCase(), demand:r.demand || "" });
    });

    const selected = [...top.map((r) => ({ side:"top", row:r })), ...worst.map((r) => ({ side:"worst", row:r }))];
    const allCodes = [...new Set(selected.flatMap((x) => byIndustry.get(`${x.row.major}${SEP}${x.row.sector}${SEP}${x.row.name}`) || []).map((x) => x.code))];
    const changes = new Map();
    let done = 0;
    await mapLimit(allCodes, 6, async (code) => {
      const text = await fetchText(`data/stocks/${encodeURIComponent(code)}.csv`, true);
      changes.set(code, text ? stockChange(text, data.date) : null);
      done++;
      if (done % 10 === 0 || done === allCodes.length) progress(`構成銘柄 ${done}/${allCodes.length}…`);
    });

    return selected.map((x) => {
      const key = `${x.row.major}${SEP}${x.row.sector}${SEP}${x.row.name}`;
      const members = (byIndustry.get(key) || []).map((m) => ({
        code:m.code, name:names.get(m.code) || m.code, demand:m.demand,
        change:changes.has(m.code) ? changes.get(m.code) : null,
        marketCapTrillion:caps.get(m.code) != null ? round(caps.get(m.code) / 1000000, 4) : null
      })).sort((a,b) => (num(b.marketCapTrillion) || -1) - (num(a.marketCapTrillion) || -1));
      return {
        side:x.side, major:x.row.major, sector:x.row.sector, industry:x.row.name,
        industryChange:round(x.row.change,4), count:Number(x.row.count)||members.length,
        members
      };
    });
  }

  async function collectNikkei(asOf) {
    const text = await fetchText("data/nikkei_ohlc.csv", true);
    if (!text) return [];
    const rows = parseCsv(text);
    return ["日経平均","日経内需株50","日経外需株50","日経半導体株指数"].map((name) => {
      const group = rows.filter((r) => String(r.name || "") === name);
      return priceMetric(name, latestPair(group, "trade_date", "close", asOf), "Nikkei指数");
    });
  }

  async function collectJpx(asOf) {
    const text = await fetchText("data/jpx_index.csv", true);
    if (!text) return [];
    const rows = parseCsv(text);
    const wanted = [
      "TOPIX (東証株価指数)","JPXプライム150指数","JPX日経インデックス400","JPX日経中小型株指数",
      "TOPIX Core30","TOPIX Large70","TOPIX 100","TOPIX Mid400","TOPIX 500","TOPIX 1000","TOPIX Small","TOPIX Small500","TOPIX Micro Cap",
      "大型","中型","小型","TOPIX バリュー","TOPIX グロース"
    ];
    return wanted.map((name) => {
      const group = rows.filter((r) => String(r.name || "") === name && String(r.trade_date || "") <= asOf)
        .sort((a,b) => String(a.trade_date).localeCompare(String(b.trade_date)));
      if (!group.length) return { name, source:"JPX", missing:true };
      const r = group[group.length - 1];
      let ch = num(r.change_pct);
      if (ch == null && group.length > 1) {
        const p = num(group[group.length - 2].close), c = num(r.close);
        if (p != null && p !== 0 && c != null) ch = (c/p-1)*100;
      }
      return { name, source:"JPX", dataDate:String(r.trade_date||""), level:round(r.close,4), changePct:round(ch,4) };
    });
  }

  async function collectOverseas(asOf) {
    const year = String(asOf).slice(0,4);
    const text = await fetchText(`data/overseas_${year}.csv`, true);
    if (!text) return [];
    const rows = parseCsv(text);
    const defs = [
      ["NYダウ","^DJI","price"],["S&P500","^GSPC","price"],["NASDAQ総合","^IXIC","price"],
      ["NASDAQ100","^NDX","price"],["Russell2000","^RUT","price"],["SOX","^SOX","price"],
      ["KOSPI","^KS11","price"],["米ドル/円","USDJPY=X","price"],["米10年債利回り","^TNX","yield"]
    ];
    return defs.map(([name, symbol, kind]) => {
      const group = rows.filter((r) => String(r.symbol || "") === symbol);
      const pair = latestPair(group, "trade_date", "close", asOf);
      return kind === "yield" ? yieldMetric(name,pair,"overseas") : priceMetric(name,pair,"overseas");
    });
  }

  async function collectSnapshot(progress) {
    progress("セクター騰落率を読んでいます…");
    const data = await fetchJson("data/sector_today.json");
    const industries = [...(data.industry || [])].filter((r) => num(r.change) != null);
    const top = [...industries].sort((a,b) => Number(b.change)-Number(a.change)).slice(0,5);
    const worst = [...industries].sort((a,b) => Number(a.change)-Number(b.change)).slice(0,5);

    const details = await collectIndustryStocks(data, top, worst, progress);
    progress("国内外の指数と金利を集めています…");
    const [nikkei, jpx, overseas, jgbText] = await Promise.all([
      collectNikkei(data.date), collectJpx(data.date), collectOverseas(data.date),
      fetchText(`data/raw/${data.date}/nikkei_jp_kabu.txt`, true)
    ]);
    const jgb = parseNikkeiJgb(jgbText, data.date);

    const snapshot = {
      kind:"market", asOf:data.date,
      methodology:{
        sectorReturns:"equal_weight_simple_average",
        marketCapUsedForReturnWeight:false,
        demandWeight:"strong=1.0, normal=0.5, balanced excluded"
      },
      japanMarket:{
        demand:marketRows(data.demand), major:marketRows(data.major),
        sector:marketRows(data.sector), industry:marketRows(data.industry),
        top5Industries:details.filter((x) => x.side === "top"),
        worst5Industries:details.filter((x) => x.side === "worst")
      },
      indices:{ nikkei, jpx, overseas, japan10Y:jgb },
      notes:[
        "米国・韓国・為替・金利は各市場で最新の確定足を使用。日本株の日付と一致しない場合はdataDateを優先して読む。",
        "日本10年国債はNikkei市場ページの長期金利欄。changeBpは掲載された前日差をbp換算。"
      ]
    };
    lastSnapshot = snapshot;
    return snapshot;
  }

  function buildPrompt(snapshot) {
    return `${MARKET_RULES}\n\n${JSON.stringify(snapshot, null, 2)}`;
  }

  function endpoint() {
    try { if (typeof AI_ENDPOINT !== "undefined" && AI_ENDPOINT) return String(AI_ENDPOINT); } catch (_) {}
    return String(window.AI_ENDPOINT || window.SectorAiEndpoint || "");
  }

  function ensureModal() {
    let modal = document.getElementById("sector-ai-modal");
    if (modal) return modal;
    modal = document.createElement("div");
    modal.id = "sector-ai-modal";
    modal.className = "hidden";
    modal.innerHTML = `<div class="sector-ai-box" role="dialog" aria-modal="true"><div class="sector-ai-head">` +
      `<strong id="sector-ai-title">本日の市況解説</strong><span id="sector-ai-copy-status"></span><span class="spacer"></span>` +
      `<button id="sector-ai-copy" type="button">コピー</button><button id="sector-ai-close" type="button">閉じる</button></div>` +
      `<pre id="sector-ai-body"></pre></div>`;
    document.body.appendChild(modal);
    const close = () => modal.classList.add("hidden");
    modal.querySelector("#sector-ai-close").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    modal.querySelector("#sector-ai-copy").addEventListener("click", async () => {
      const text = modal.querySelector("#sector-ai-body").textContent || "";
      const note = modal.querySelector("#sector-ai-copy-status");
      try { await navigator.clipboard.writeText(text); note.textContent = "コピー済み"; }
      catch (_) { note.textContent = "コピー失敗"; }
    });
    return modal;
  }

  function showModal(title, text) {
    const modal = ensureModal();
    modal.querySelector("#sector-ai-title").textContent = title;
    modal.querySelector("#sector-ai-copy-status").textContent = "";
    modal.querySelector("#sector-ai-body").textContent = text;
    modal.classList.remove("hidden");
  }

  function setBusy(on, status) {
    busy = on;
    const run = document.getElementById("sector-ai-run");
    const prompt = document.getElementById("sector-ai-prompt");
    if (run) run.disabled = on;
    if (prompt) prompt.disabled = on;
    const note = document.getElementById("sector-ai-status");
    if (note) note.textContent = status || "";
  }

  async function promptOutput() {
    if (busy) return;
    setBusy(true, "市況データを作成中…");
    try {
      const snapshot = await collectSnapshot((s) => setBusy(true,s));
      const prompt = buildPrompt(snapshot);
      showModal("本日の市況解説・AI分析用プロンプト", prompt);
      setBusy(false, `${snapshot.asOf}　プロンプト ${(prompt.length/1024).toFixed(1)}KB`);
    } catch (e) {
      setBusy(false, "プロンプト作成失敗");
      showModal("作成できませんでした", String(e && e.message ? e.message : e));
    }
  }

  async function runAnalysis() {
    if (busy) return;
    setBusy(true, "市況データを作成中…");
    try {
      const snapshot = await collectSnapshot((s) => setBusy(true,s));
      const url = endpoint();
      if (!url) throw new Error("AIの中継先が設定されていない");
      const body = JSON.stringify(snapshot);
      setBusy(true, `Geminiの高級AIに送信 ${(body.length/1024).toFixed(1)}KB…`);
      const res = await fetch(url, { method:"POST", mode:"cors", headers:{"content-type":"application/json"}, body });
      const raw = await res.text();
      if (!res.ok) throw new Error(`HTTP ${res.status}\n${raw}`);
      let answer = raw;
      try { const j = JSON.parse(raw); answer = j.text || j.error || raw; } catch (_) {}
      showModal(`本日の市況解説 ${snapshot.asOf}`, answer);
      setBusy(false, `${snapshot.asOf}　AI分析完了`);
    } catch (e) {
      setBusy(false, "AI分析失敗");
      showModal("AI分析できませんでした", `${String(e && e.message ? e.message : e)}\n\n※「AI分析用プロンプト出力」はAPIを使わず利用できます。`);
    }
  }

  function installStyle() {
    if (document.getElementById("sector-ai-style")) return;
    const style = document.createElement("style");
    style.id = "sector-ai-style";
    style.textContent = `
      #sector-page #sector-ai-run,#sector-page #sector-ai-prompt { white-space:nowrap; }
      #sector-page #sector-ai-run:disabled,#sector-page #sector-ai-prompt:disabled { color:var(--dim); border-color:var(--dim); cursor:default; }
      #sector-page #sector-ai-status { padding:4px 5px; color:var(--fg); font-size:12px; white-space:nowrap; }
      #sector-ai-modal { position:fixed; inset:0; z-index:10060; display:flex; align-items:center; justify-content:center; padding:14px; background:rgba(0,0,0,.76); }
      #sector-ai-modal.hidden { display:none !important; }
      #sector-ai-modal .sector-ai-box { width:min(1200px,97vw); height:min(90vh,980px); display:flex; flex-direction:column; background:var(--bg); color:var(--fg); border:2px solid var(--line); }
      #sector-ai-modal .sector-ai-head { display:flex; align-items:center; gap:9px; padding:7px 9px; border-bottom:1px solid var(--line); background:var(--panel); }
      #sector-ai-modal .sector-ai-head strong { color:var(--fg2); font-size:16px; }
      #sector-ai-modal .sector-ai-head .spacer { flex:1; }
      #sector-ai-modal .sector-ai-head button { background:var(--panel); color:var(--fg); border:1px solid var(--line); font:inherit; padding:4px 12px; cursor:pointer; }
      #sector-ai-copy-status { color:var(--dim); font-size:12px; }
      #sector-ai-body { flex:1; overflow:auto; margin:0; padding:13px; white-space:pre-wrap; overflow-wrap:anywhere; font:inherit; line-height:1.65; user-select:text; }
      @media(max-width:760px){ #sector-page .bar { flex-wrap:wrap; } #sector-page #sector-ai-status { width:100%; } #sector-ai-modal { padding:5px; } }
    `;
    document.head.appendChild(style);
  }

  function init() {
    const page = document.getElementById("sector-page");
    const toggle = document.getElementById("sector-view-toggle");
    const bar = page && page.querySelector(".bar");
    if (!page || !bar || !toggle) return false;
    if (document.getElementById("sector-ai-run")) return true;
    installStyle();
    ensureModal();
    const run = document.createElement("button");
    run.id = "sector-ai-run"; run.type = "button"; run.textContent = "APIによるAI分析";
    run.title = "当日のセクター・業種・国内外指数・為替・金利をGeminiの高級AIがまとめて市況解説する";
    const prompt = document.createElement("button");
    prompt.id = "sector-ai-prompt"; prompt.type = "button"; prompt.textContent = "AI分析用プロンプト出力";
    prompt.title = "本日の市況データを集め、各自のAIに貼れる分析用プロンプトを出力する";
    const status = document.createElement("span"); status.id = "sector-ai-status";
    toggle.insertAdjacentElement("afterend", prompt);
    toggle.insertAdjacentElement("afterend", run);
    prompt.insertAdjacentElement("afterend", status);
    run.addEventListener("click", runAnalysis);
    prompt.addEventListener("click", promptOutput);
    document.addEventListener("keydown", (e) => {
      const modal = document.getElementById("sector-ai-modal");
      if (e.key === "Escape" && modal && !modal.classList.contains("hidden")) {
        modal.classList.add("hidden"); e.preventDefault(); e.stopImmediatePropagation();
      }
    }, true);
    window.SectorMarketAI = { collect:collectSnapshot, prompt:buildPrompt, run:runAnalysis, last:() => lastSnapshot };
    return true;
  }

  if (!init()) {
    const ob = new MutationObserver(() => { if (init()) ob.disconnect(); });
    ob.observe(document.documentElement, { childList:true, subtree:true });
  }
})();
