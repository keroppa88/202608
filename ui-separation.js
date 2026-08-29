(function () {
  "use strict";
  if (typeof document === "undefined") return;

  const menu = document.getElementById("titleMenu");
  if (menu) {
    menu.innerHTML = [
      '<button data-go="ai" aria-selected="true">AI分析</button>',
      '<button data-go="sheet">表</button>',
      '<button data-go="chart">チャート</button>',
      '<button data-go="correlation">相関係数</button>',
      '<button data-go="technical">テクニカル</button>'
    ].join("");
  }
  const newItems = menu ? [...menu.querySelectorAll("button")] : [];
  let menuCursor = 0;
  function drawMenuCursor() {
    newItems.forEach((button, i) => button.setAttribute("aria-selected", String(i === menuCursor)));
  }

  const style = document.createElement("style");
  style.textContent = `
    #ai-analysis, #correlation-page { height:100%; display:flex; flex-direction:column; }
    #technical #technical-splitter,
    #technical #technical-bottom,
    #technical #tcomp,
    #technical #tauto,
    #technical #tai,
    #technical #ttxt { display:none !important; }
    #technical .technical-top { flex:1 1 auto !important; flex-basis:auto !important; min-height:0; }
    #correlation-page .technical-bottom { display:flex !important; flex:1 1 auto; min-height:0; }
    #ai-analysis .ai-wrap {
      width:min(920px, 100%); margin:0 auto; padding:18px 14px 28px;
      overflow:auto; flex:1; scrollbar-color:var(--fg) var(--bg); scrollbar-width:thin;
    }
    #ai-analysis .ai-row {
      display:grid; grid-template-columns:170px minmax(0, 1fr); gap:10px;
      align-items:center; margin-bottom:12px;
    }
    #ai-analysis .ai-label { color:var(--fg2); }
    #ai-analysis select,
    #ai-analysis .ai-add,
    #ai-analysis .ai-top-action,
    #ai-analysis .ai-sub button {
      background:var(--panel); color:var(--fg); border:1px solid var(--line);
      font:inherit; padding:5px 8px;
    }
    #ai-analysis select { width:100%; min-width:0; }
    #ai-analysis .ai-subs { display:flex; flex-direction:column; gap:6px; }
    #ai-analysis .ai-sub { display:flex; gap:6px; align-items:center; }
    #ai-analysis .ai-sub select { flex:1; }
    #ai-analysis .ai-sub button { cursor:pointer; padding:5px 10px; }
    #ai-analysis .ai-add { cursor:pointer; margin-top:2px; }
    #ai-analysis .ai-top-action { cursor:pointer; padding:5px 12px; }
    #ai-analysis .ai-top-action:disabled,
    #ai-analysis .ai-add:disabled { color:var(--dim); border-color:var(--dim); cursor:default; }
    #ai-analysis .ai-result {
      min-height:160px; border-top:1px solid var(--line); margin-top:14px; padding-top:12px;
      white-space:pre-wrap; line-height:1.8;
    }
    #ai-analysis .ai-empty { color:var(--dim); }
    #ai-prompt-modal {
      position:fixed; inset:0; z-index:10000; background:rgba(0,0,0,.72);
      display:flex; align-items:center; justify-content:center; padding:16px;
    }
    #ai-prompt-modal.hidden { display:none !important; }
    #ai-prompt-box {
      width:min(1100px, 96vw); height:min(86vh, 900px); background:var(--bg); color:var(--fg);
      border:2px solid var(--line); display:flex; flex-direction:column; min-height:240px;
    }
    #ai-prompt-head {
      display:flex; align-items:center; gap:8px; padding:6px 8px; border-bottom:1px solid var(--line);
      background:var(--panel); flex:none;
    }
    #ai-prompt-head .title { color:var(--fg2); }
    #ai-prompt-head .spacer { flex:1; }
    #ai-prompt-head button {
      background:var(--panel); color:var(--fg); border:1px solid var(--line); font:inherit;
      padding:4px 12px; cursor:pointer;
    }
    #ai-prompt-copy-status { color:var(--dim); font-size:12px; }
    #ai-prompt-text {
      flex:1; margin:0; padding:12px; overflow:auto; white-space:pre-wrap; overflow-wrap:anywhere;
      font:inherit; line-height:1.55; user-select:text;
    }
    @media (max-width:760px) {
      #ai-analysis .bar { flex-wrap:wrap; }
      #ai-analysis .bar .spacer { display:none; }
      #ai-analysis #aistatus { width:100%; }
    }
    @media (max-width:640px) {
      #ai-analysis .ai-row { grid-template-columns:1fr; gap:5px; }
      #ai-analysis .ai-top-action { padding:5px 8px; }
    }
  `;
  document.head.appendChild(style);

  const aiPage = document.createElement("section");
  aiPage.id = "ai-analysis";
  aiPage.className = "hidden";
  aiPage.innerHTML = `
    <div class="bar">
      <button id="aiback" title="タイトルへ戻る">戻る</button>
      <button id="aitheme" title="押すたびに配色が変わる">Color</button>
      <button id="ai-run" class="ai-top-action" title="APIでAI分析する">APIによるAI分析</button>
      <button id="ai-prompt" class="ai-top-action" title="他のAIへ貼り付ける分析用プロンプトを出力する">AI分析用プロンプト出力</button>
      <div class="spacer"></div>
      <div class="note" id="aistatus"></div>
    </div>
    <div class="ai-wrap">
      <div class="ai-row">
        <div class="ai-label">予測対象銘柄</div>
        <select id="ai-main" aria-label="予測対象銘柄"></select>
      </div>
      <div class="ai-row">
        <div class="ai-label">分析用比較銘柄 <span id="ai-sub-count">0/10</span></div>
        <div>
          <div id="ai-subs" class="ai-subs"></div>
          <button id="ai-add" class="ai-add">＋ 比較銘柄</button>
        </div>
      </div>
      <div id="ai-result" class="ai-result"><span class="ai-empty">銘柄を選び、上部の「APIによるAI分析」または「AI分析用プロンプト出力」を押す。</span></div>
    </div>`;

  const promptModal = document.createElement("div");
  promptModal.id = "ai-prompt-modal";
  promptModal.className = "hidden";
  promptModal.innerHTML = `
    <div id="ai-prompt-box" role="dialog" aria-modal="true" aria-label="AI分析用プロンプト">
      <div id="ai-prompt-head">
        <span class="title">AI分析用プロンプト</span>
        <span id="ai-prompt-copy-status"></span>
        <div class="spacer"></div>
        <button id="ai-prompt-copy">コピー</button>
        <button id="ai-prompt-close">×</button>
      </div>
      <pre id="ai-prompt-text"></pre>
    </div>`;

  const corrPage = document.createElement("section");
  corrPage.id = "correlation-page";
  corrPage.className = "hidden";
  corrPage.innerHTML = `
    <div class="bar">
      <button id="rcback" title="タイトルへ戻る">戻る</button>
      <button id="rtheme" title="押すたびに配色が変わる">Color</button>
      <div class="spacer"></div>
    </div>`;

  const saver = document.getElementById("saver");
  if (saver) {
    document.body.insertBefore(aiPage, saver);
    document.body.insertBefore(corrPage, saver);
    document.body.insertBefore(promptModal, saver);
  } else {
    document.body.append(aiPage, corrPage, promptModal);
  }

  let aiCatalog = [];
  let aiMainChoices = [];
  let aiCompareChoices = [];
  let aiBusy = false;
  const MAX_SUBS = 10;

  // メインは250足、比較は40足の見込みがある系列だけを出す。
  // Yahoo系列は選択銘柄だけを年ごとに抽出するため、メイン候補にも戻している。
  async function prepareAiChoices(year) {
    const counts = new Map();
    const latest = new Map();
    const addCounts = (src, rows, field) => {
      for (const row of rows) {
        const id = row[field];
        if (!id) continue;
        const key = `${src}:${id}`;
        counts.set(key, (counts.get(key) || 0) + 1);
        if (row.trade_date && (!latest.has(key) || row.trade_date > latest.get(key))) latest.set(key, row.trade_date);
      }
    };
    addCounts("yahoo", await fetchCsv(`data/overseas_${year}.csv`), "symbol");
    addCounts("jpx", await fetchCsv("data/jpx_index.csv"), "name");
    addCounts("nikkei", await fetchCsv("data/nikkei_ohlc.csv"), "name");
    addCounts("yomiuri", await fetchCsv("data/yomiuri333.csv"), "name");
    addCounts("ratio", await fetchCsv("data/ratios.csv"), "name");
    addCounts("rates", await fetchCsv("data/rates.csv"), "name");

    const stockSpan = new Map((await fetchCsv("data/stocks/list.csv")).map((row) => {
      const first = Date.parse(`${row.first || ""}T00:00:00Z`);
      const last = Date.parse(`${row.last || ""}T00:00:00Z`);
      return [`stock:${row.code}`, Number.isFinite(first) && Number.isFinite(last) ? (last - first) / 86400000 : 0];
    }));
    const sourceOf = (item) => splitKey(item.key)[0];
    aiMainChoices = aiCatalog.filter((item) => {
      const src = sourceOf(item);
      if (src === "original") return false;
      if (src === "stock") return (stockSpan.get(item.key) || 0) >= 400;
      if (src === "yahoo") return (counts.get(item.key) || 0) >= 40;
      return (counts.get(item.key) || 0) >= 250 && String(latest.get(item.key) || "").startsWith(year);
    });
    aiCompareChoices = aiCatalog.filter((item) => {
      const src = sourceOf(item);
      if (src === "original") return false;
      if (src === "stock") return (stockSpan.get(item.key) || 0) >= 90;
      return (counts.get(item.key) || 0) >= 40 && String(latest.get(item.key) || "").startsWith(year);
    });
  }

  const FALLBACK_TECH_RULES = `次のJSONは、ある銘柄（name）について、プログラムが計算した
テクニカル指標と、主要指数などとの相関です。この数字だけを使って日本語で述べてください。

守ること
- JSONに無いことは書かない。会社の事情や出来事は知らないものとして扱う
- 過去に似た局面があったという話を、これからそうなるという話にしない
- 材料が足りない項目は、足りないと書く
- 使った期間（span）に必ず触れる。何年ぶんを見て言っているのかを最初に書く
- 見出しと箇条書きで、本文は1200字程度。そのあとに点数を付ける

書く順
1. 何年ぶんを見たか（span）。params.base が既定の数字、params.tuned がこの銘柄に合わせて選び直した数字。両方を並べて、違いが大きい指標があれば触れる
2. 長期のトレンド … base と tuned の移動平均・移動平均乖離、slope2 / order / chg100 / chg200 / pos52 / dev2。いま上か下か、いつからそうなのか
3. 短期のトレンド … tuned.recent の chg5 / chg10 / dev0 / rsi / stK / stD / macdH / macdHR / bbB / run / gap / range
4. 指標ごとの状態と経緯 … tuned.back の 20/40/60/80/100/150/200日前と今を比べる。dMaS / dMaL / dMacd / dSar / dStoch / dRsi はその向きになってからの日数（符号が向き）
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
- like.hits の dist は今との近さ（0 に近いほど似ている）。fwd はその日から5/10/20/60日後の騰落率%。同じ年からは3件までしか入れていない
- corr の中身は相関の計算結果。r が相関、r60Ago は60日前の値、regime はメインが上げていた局面と下げていた局面で分けた相関
- null は計算できなかったところ`;

  function signature() {
    return [settings.corrAiMain, ...(settings.corrAiSubs || [])].join("\n");
  }

  function clearAiResult() {
    const result = document.getElementById("ai-result");
    if (result) result.innerHTML = '<span class="ai-empty">条件を選び、上部の分析ボタンを押す。</span>';
  }

  function setAiEnabled(enabled) {
    document.getElementById("ai-main").disabled = !enabled;
    document.getElementById("ai-run").disabled = !enabled;
    document.getElementById("ai-prompt").disabled = !enabled;
    document.getElementById("ai-add").disabled = !enabled || settings.corrAiSubs.length >= MAX_SUBS;
    document.querySelectorAll("#ai-subs select, #ai-subs button").forEach((el) => { el.disabled = !enabled; });
  }

  function normalizeAiSelection() {
    const hasMain = (key) => aiMainChoices.some((c) => c.key === key);
    const hasCompare = (key) => aiCompareChoices.some((c) => c.key === key);
    if (!settings.corrAiMain || !hasMain(settings.corrAiMain)) {
      settings.corrAiMain = hasMain(settings.techKey) ? settings.techKey : (aiMainChoices[0] ? aiMainChoices[0].key : "");
    }
    settings.corrAiSubs = [...new Set(settings.corrAiSubs || [])]
      .filter((key) => hasCompare(key) && key !== settings.corrAiMain)
      .slice(0, MAX_SUBS);
    saveSettings();
  }

  function drawAiControls() {
    const main = document.getElementById("ai-main");
    main.innerHTML = "";
    fillPicker(main, aiMainChoices, settings.corrAiMain, false);
    main.value = settings.corrAiMain;
    main.onchange = () => {
      settings.corrAiMain = main.value;
      settings.corrAiSubs = settings.corrAiSubs.filter((key) => key !== settings.corrAiMain);
      saveSettings();
      clearAiResult();
      drawAiControls();
    };

    const subs = document.getElementById("ai-subs");
    subs.innerHTML = "";
    settings.corrAiSubs.forEach((key, i) => {
      const row = document.createElement("div");
      row.className = "ai-sub";
      const sel = document.createElement("select");
      sel.setAttribute("aria-label", `分析用比較銘柄 ${i + 1}`);
      fillPicker(sel, aiCompareChoices, key, false);
      sel.value = key;
      sel.addEventListener("change", () => {
        const next = sel.value;
        if (next === settings.corrAiMain || settings.corrAiSubs.some((k, j) => j !== i && k === next)) {
          sel.value = settings.corrAiSubs[i];
          document.getElementById("aistatus").textContent = "同じ銘柄は重複して選べない";
          return;
        }
        settings.corrAiSubs[i] = next;
        saveSettings();
        clearAiResult();
      });
      const del = document.createElement("button");
      del.textContent = "×";
      del.title = "比較銘柄から外す";
      del.addEventListener("click", () => {
        settings.corrAiSubs.splice(i, 1);
        saveSettings();
        clearAiResult();
        drawAiControls();
      });
      row.append(sel, del);
      subs.appendChild(row);
    });
    document.getElementById("ai-sub-count").textContent = `${settings.corrAiSubs.length}/${MAX_SUBS}`;
    document.getElementById("ai-add").disabled = aiBusy || settings.corrAiSubs.length >= MAX_SUBS;
  }

  async function openAiPage() {
    titleEl.classList.add("hidden");
    corrPage.classList.add("hidden");
    aiPage.classList.remove("hidden");
    document.getElementById("aistatus").textContent = "銘柄一覧を読み込み中…";
    try {
      if (!aiCatalog.length) {
        const year = String(new Date().getFullYear());
        aiCatalog = await buildCatalog(year);
        await prepareAiChoices(year);
      }
      normalizeAiSelection();
      drawAiControls();
      document.getElementById("aistatus").textContent = "";
    } catch (e) {
      document.getElementById("aistatus").textContent = `銘柄一覧を読めなかった: ${e && e.message ? e.message : e}`;
    }
  }

  function closeAiPage() {
    closePromptModal();
    aiPage.classList.add("hidden");
    titleEl.classList.remove("hidden");
  }

  function openCorrelationPage() {
    titleEl.classList.add("hidden");
    aiPage.classList.add("hidden");
    corrPage.classList.remove("hidden");
    renderCorrelations();
  }

  function closeCorrelationPage() {
    closeCorrInfo();
    corrPage.classList.add("hidden");
    titleEl.classList.remove("hidden");
  }

  async function buildStandaloneAiPayload(progress) {
    const key = settings.corrAiMain;
    const endYear = new Date().getFullYear();

    progress("価格を読んでいます…");
    const rows = await techRows(key, endYear, AI_TECH_YEARS);
    if (rows.length < 250) throw new Error(`足が ${rows.length}日しかない`);
    const at = rows.length - 1;
    const catalog = aiCatalog.length ? aiCatalog : await buildCatalog(String(endYear));
    const name = labelOf(key, catalog);
    const from = Math.min(250, Math.floor(rows.length / 4));

    progress("既定の数字で見ています…");
    const base = JSON.parse(JSON.stringify(DEFAULT_TECH_PARAMS));
    const indBase = techIndicators(rows, base);

    progress("いちばん合う数字を探しています…");
    const tuned = techAutoFit(rows, from, rows.length - 1, base);
    const indTuned = techIndicators(rows, tuned);

    progress("似た局面を探しています…");
    const like = {
      short: aiLike(indTuned, rows, AI_LIKE_SHORT, at),
      long: aiLike(indTuned, rows, AI_LIKE_LONG, at)
    };

    const backRow = (ind, fields) => {
      const out = {};
      AI_TECH_BACK.forEach((n) => {
        const i = at - n;
        out[n] = i >= 0 ? aiTechRow(ind, rows, i, fields) : null;
      });
      return out;
    };
    const recent = [];
    for (let i = Math.max(0, at - AI_TECH_RECENT + 1); i <= at; i++) {
      recent.push(aiTechRow(indTuned, rows, i, AI_TECH_FIELDS));
    }

    progress(settings.corrAiSubs.length ? "比較銘柄との関係を計算しています…" : "分析データをまとめています…");
    let corr = null;
    try {
      corr = await buildCorrAiPayload(catalog, progress);
    } catch (e) {
      corr = { error: String(e && e.message ? e.message : e) };
    }

    return {
      kind: "tech",
      name,
      asOf: rows[at].d,
      span: {
        from: rows[0].d,
        to: rows[at].d,
        rows: rows.length,
        years: aiRound(rows.length / 250, 1)
      },
      params: { base, tuned },
      base: {
        now: aiTechRow(indBase, rows, at, AI_BASE_FIELDS),
        back: backRow(indBase, AI_BASE_FIELDS)
      },
      tuned: {
        recent,
        back: backRow(indTuned, AI_TECH_FIELDS)
      },
      like,
      corr
    };
  }

  function openPromptModal(text) {
    document.getElementById("ai-prompt-text").textContent = text;
    document.getElementById("ai-prompt-copy-status").textContent = "";
    promptModal.classList.remove("hidden");
  }

  function closePromptModal() {
    promptModal.classList.add("hidden");
  }

  async function copyPrompt() {
    const text = document.getElementById("ai-prompt-text").textContent;
    const note = document.getElementById("ai-prompt-copy-status");
    try {
      await navigator.clipboard.writeText(text);
      note.textContent = "コピー済み";
    } catch (_) {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        ta.remove();
        note.textContent = "コピー済み";
      } catch (e) {
        note.textContent = "コピーできなかった";
      }
    }
  }

  async function runAiPromptOutput() {
    if (aiBusy || !settings.corrAiMain) return;
    aiBusy = true;
    setAiEnabled(false);
    const button = document.getElementById("ai-prompt");
    const status = document.getElementById("aistatus");
    button.textContent = "作成中…";
    const progress = (text) => { status.textContent = text; };
    try {
      const payload = await buildStandaloneAiPayload(progress);
      const prompt = `${FALLBACK_TECH_RULES}\n\n${JSON.stringify(payload)}`;
      openPromptModal(prompt);
      status.textContent = `${payload.name}　${payload.asOf}　プロンプト ${(prompt.length / 1024).toFixed(1)}KB`;
    } catch (e) {
      document.getElementById("ai-result").textContent = `プロンプトを作れなかった\n${e && e.message ? e.message : e}`;
      status.textContent = "プロンプト出力に失敗";
    } finally {
      aiBusy = false;
      button.textContent = "AI分析用プロンプト出力";
      setAiEnabled(true);
      drawAiControls();
    }
  }

  async function diagnoseLoadFailure(original) {
    if (!AI_ENDPOINT) return "AIの中継先が設定されていない";
    try {
      const r = await fetch(`${AI_ENDPOINT}/prompt`, { method: "GET", cache: "no-store", mode: "cors" });
      if (!r.ok) return `AI中継には到達したが /prompt が HTTP ${r.status}`;
      return `AI中継の /prompt には到達できた。POST送信側で失敗している可能性がある。\n元のエラー: ${original}`;
    } catch (e) {
      return `AI中継にブラウザから接続できない。Cloudflare Worker の稼働状態と CORS（ALLOWED_ORIGINS）を確認。\n${AI_ENDPOINT}\n元のエラー: ${original}`;
    }
  }

  async function runAiAnalysis() {
    if (aiBusy || !settings.corrAiMain) return;
    aiBusy = true;
    setAiEnabled(false);
    const run = document.getElementById("ai-run");
    const status = document.getElementById("aistatus");
    const result = document.getElementById("ai-result");
    run.textContent = "分析中…";
    const requested = signature();
    const progress = (text) => { status.textContent = text; };
    try {
      const payload = await buildStandaloneAiPayload(progress);
      const body = JSON.stringify(payload);
      progress(`送信 ${(body.length / 1024).toFixed(1)}KB`);
      if (!AI_ENDPOINT) throw new Error("AIの中継先が設定されていない");
      const res = await fetch(AI_ENDPOINT, {
        method: "POST",
        mode: "cors",
        headers: { "content-type": "application/json" },
        body
      });
      const raw = await res.text();
      if (!res.ok) throw new Error(`HTTP ${res.status}\n${raw}`);
      let answer = raw;
      try {
        const json = JSON.parse(raw);
        answer = json.text || json.error || raw;
      } catch (_) { }
      if (requested !== signature()) {
        status.textContent = "分析中に条件が変わったため結果を破棄した";
        return;
      }
      result.textContent = answer;
      status.textContent = `${payload.name}　${payload.asOf}　比較 ${settings.corrAiSubs.length}銘柄`;
    } catch (e) {
      const message = String(e && e.message ? e.message : e);
      if (/load failed|failed to fetch|networkerror/i.test(message)) {
        result.textContent = `分析できなかった\n${await diagnoseLoadFailure(message)}\n\n※「AI分析用プロンプト出力」はAPIを使わないため利用できる。`;
      } else {
        result.textContent = `分析できなかった\n${message}`;
      }
      status.textContent = "AI分析に失敗";
    } finally {
      aiBusy = false;
      run.textContent = "APIによるAI分析";
      setAiEnabled(true);
      drawAiControls();
    }
  }

  const initSeparatedUi = () => {
    const bottom = document.getElementById("technical-bottom");
    if (bottom) corrPage.appendChild(bottom);

    const oldBackToTitle = backToTitle;
    backToTitle = function () {
      closePromptModal();
      aiPage.classList.add("hidden");
      corrPage.classList.add("hidden");
      oldBackToTitle();
    };

    openTechnical = function () {
      titleEl.classList.add("hidden");
      techEl.classList.remove("hidden");
      drawTechParams();
      drawTechnical();
    };
    backFromTechnical = function () {
      closeTechChart();
      closeTechCompare();
      closeTechPick();
      techEl.classList.add("hidden");
      titleEl.classList.remove("hidden");
    };
    pickTechKey = function (key) {
      closeTechPick();
      if (key === settings.techKey) return;
      settings.techKey = key;
      saveSettings();
      drawTechnical();
    };

    setCorrAiDefaults = function (catalog) {
      const has = (key) => catalog.some((c) => c.key === key);
      if (!settings.corrAiMain || !has(settings.corrAiMain)) {
        settings.corrAiMain = settings.corrColumns.find(has) || (catalog[0] ? catalog[0].key : "");
      }
      settings.corrAiSubs = [...new Set(settings.corrAiSubs || [])]
        .filter((key) => has(key) && key !== settings.corrAiMain)
        .slice(0, MAX_AI_SUBS);
      saveSettings();
    };

    const openMenuItem = (button) => {
      if (!button || button.disabled) return;
      const go = button.dataset.go;
      if (go === "ai") openAiPage();
      else if (go === "sheet") openSheet();
      else if (go === "chart") openCharts();
      else if (go === "correlation") openCorrelationPage();
      else if (go === "technical") openTechnical();
    };
    newItems.forEach((button, i) => {
      button.addEventListener("mouseenter", () => { menuCursor = i; drawMenuCursor(); });
      button.addEventListener("click", () => { menuCursor = i; drawMenuCursor(); openMenuItem(button); });
    });
    drawMenuCursor();

    document.getElementById("aiback").addEventListener("click", closeAiPage);
    document.getElementById("aitheme").addEventListener("click", nextTheme);
    document.getElementById("rcback").addEventListener("click", closeCorrelationPage);
    document.getElementById("rtheme").addEventListener("click", () => {
      nextTheme();
      if (corrState) drawCorrelationResults();
    });
    document.getElementById("ai-run").addEventListener("click", runAiAnalysis);
    document.getElementById("ai-prompt").addEventListener("click", runAiPromptOutput);
    document.getElementById("ai-prompt-copy").addEventListener("click", copyPrompt);
    document.getElementById("ai-prompt-close").addEventListener("click", closePromptModal);
    promptModal.addEventListener("click", (e) => { if (e.target === promptModal) closePromptModal(); });
    document.getElementById("ai-add").addEventListener("click", () => {
      if (settings.corrAiSubs.length >= MAX_SUBS) return;
      const first = aiCompareChoices.find((c) => c.key !== settings.corrAiMain && !settings.corrAiSubs.includes(c.key));
      if (!first) return;
      settings.corrAiSubs.push(first.key);
      saveSettings();
      clearAiResult();
      drawAiControls();
    });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", initSeparatedUi, { once: true });
  else initSeparatedUi();

  document.addEventListener("keydown", (e) => {
    if (!promptModal.classList.contains("hidden")) {
      if (e.key === "Escape") {
        closePromptModal();
        e.preventDefault();
      }
      e.stopImmediatePropagation();
      return;
    }
    if (!titleEl.classList.contains("hidden")) {
      if (e.key === "ArrowDown") {
        menuCursor = (menuCursor + 1) % newItems.length;
        drawMenuCursor();
        e.preventDefault();
        e.stopImmediatePropagation();
      } else if (e.key === "ArrowUp") {
        menuCursor = (menuCursor - 1 + newItems.length) % newItems.length;
        drawMenuCursor();
        e.preventDefault();
        e.stopImmediatePropagation();
      } else if (e.key === "Enter") {
        const button = newItems[menuCursor];
        if (button) button.click();
        e.preventDefault();
        e.stopImmediatePropagation();
      }
      return;
    }
    const active = !aiPage.classList.contains("hidden") || !corrPage.classList.contains("hidden");
    if (!active) return;
    if (e.key === "Escape") {
      if (!corrInfoModal.classList.contains("hidden")) closeCorrInfo();
      else if (!aiPage.classList.contains("hidden")) closeAiPage();
      else closeCorrelationPage();
      e.preventDefault();
    }
    e.stopImmediatePropagation();
  }, true);
})();
